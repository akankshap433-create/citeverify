import logging
import re
from typing import Any, Dict, List

import httpx
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.services.citation_utils import apa_citation, doi_url, fallback_query, rank_candidates
from app.services.research_api import clean_xml_tags, reconstruct_abstract
from app.services.verifier import get_genai_client

logger = logging.getLogger("citeverify")
MODEL = "gemini-3.5-flash-lite"


class _Query(BaseModel):
    query: str


class _Why(BaseModel):
    index: int
    why: str


class _WhyList(BaseModel):
    items: List[_Why]


async def _gemini(prompt: str, schema):
    client = get_genai_client()
    r = await client.aio.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0.2),
    )
    return schema.model_validate(r.parsed) if r.parsed is not None else schema.model_validate_json(r.text)


async def build_query(claim: str) -> str:
    try:
        q = (await _gemini(
            "Turn this scientific claim into one concise academic search query (4 to 10 keywords). "
            "No author names, no years, no quotation marks, no boolean operators.\n\nClaim: " + claim,
            _Query,
        )).query
        q = re.sub(r'["\n]+', " ", q).strip()
        if q:
            return q
    except Exception as e:
        logger.warning(f"Gemini query generation failed: {e}")
    return fallback_query(claim)


def _headers() -> Dict[str, str]:
    return {"User-Agent": f"CiteVerify/1.0 (mailto:{settings.OPENALEX_EMAIL or 'citeverify@example.com'})"}


async def _openalex(query: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    params = {"search": query, "filter": "has_abstract:true", "per-page": 12,
              "select": "id,doi,title,display_name,publication_year,authorships,abstract_inverted_index,cited_by_count"}
    if settings.OPENALEX_EMAIL:
        params["mailto"] = settings.OPENALEX_EMAIL
    try:
        r = await client.get("https://api.openalex.org/works", params=params, headers=_headers())
        if r.status_code != 200:
            return []
        out = []
        for w in r.json().get("results", []):
            doi = w.get("doi")
            out.append({
                "title": w.get("title") or w.get("display_name") or "",
                "authors": [a.get("author", {}).get("display_name") for a in w.get("authorships", []) if a.get("author", {}).get("display_name")],
                "year": w.get("publication_year"), "doi": doi, "url": doi or w.get("id"),
                "abstract": reconstruct_abstract(w.get("abstract_inverted_index")), "cited_by": w.get("cited_by_count", 0),
            })
        return out
    except Exception as e:
        logger.warning(f"OpenAlex suggest search failed: {e}")
        return []


async def _crossref(query: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    params = {"query.bibliographic": query, "rows": 12, "filter": "has-abstract:true",
              "select": "DOI,title,author,issued,created,abstract,URL,is-referenced-by-count"}
    try:
        r = await client.get("https://api.crossref.org/works", params=params, headers=_headers())
        if r.status_code != 200:
            return []
        out = []
        for it in r.json().get("message", {}).get("items", []):
            t = it.get("title") or [""]
            parts = ((it.get("issued") or it.get("created") or {}).get("date-parts") or [[None]])[0]
            out.append({
                "title": t[0],
                "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "") for a in it.get("author", [])],
                "year": parts[0] if parts else None,
                "doi": doi_url(it.get("DOI")), "url": it.get("URL"),
                "abstract": clean_xml_tags(it.get("abstract", "")), "cited_by": it.get("is-referenced-by-count", 0),
            })
        return out
    except Exception as e:
        logger.warning(f"Crossref suggest search failed: {e}")
        return []


async def _explain(claim: str, papers: List[Dict[str, Any]]) -> Dict[int, str]:
    listing = "\n\n".join(f"[{i}] {p['title']} ({p.get('year')})\nAbstract: {p['abstract'][:700]}" for i, p in enumerate(papers))
    try:
        res = await _gemini(
            "For each paper below, write ONE sentence (max 25 words) explaining how it supports or informs this claim. "
            "Use only what the abstract says. If a paper is only loosely related, say so honestly.\n\n"
            f"Claim: {claim}\n\n{listing}\n\nReturn items with the paper index and the sentence.",
            _WhyList,
        )
        return {x.index: x.why.strip() for x in res.items}
    except Exception as e:
        logger.warning(f"Gemini explanation failed: {e}")
        return {}


async def suggest_citations(claim_text: str) -> Dict[str, Any]:
    query = await build_query(claim_text)
    logger.info(f"Suggest citations -> query='{query}'")
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
        cands = await _openalex(query, client)
        picks = rank_candidates(cands)
        if len(picks) < 2:
            picks = rank_candidates(cands + await _crossref(query, client))
    why = await _explain(claim_text, picks) if picks else {}
    return {
        "query": query,
        "suggestions": [{
            "title": p["title"], "authors": p["authors"][:8], "year": p.get("year"),
            "doi": doi_url(p.get("doi")), "url": p.get("url") or doi_url(p.get("doi")),
            "why": why.get(i) or "Related work on this topic. Check the abstract to confirm it fits your claim.",
            "apa": apa_citation(p),
        } for i, p in enumerate(picks)],
    }
