import difflib
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """
    Reconstructs plain-text abstract from an OpenAlex abstract_inverted_index.
    The inverted index maps words to lists of 0-based token positions.
    """
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""

    pos_word_map: Dict[int, str] = {}
    for word, positions in inverted_index.items():
        if isinstance(positions, (list, tuple)):
            for pos in positions:
                if isinstance(pos, int):
                    pos_word_map[pos] = word

    if not pos_word_map:
        return ""

    max_position = max(pos_word_map.keys())
    words = [pos_word_map.get(i, "") for i in range(max_position + 1)]
    reconstructed = " ".join(words)
    # Normalize multiple whitespace characters
    cleaned = re.sub(r"\s+", " ", reconstructed).strip()
    return cleaned


def clean_xml_tags(text: str) -> str:
    """Strips XML/HTML tags often present in Crossref abstracts."""
    if not text:
        return ""
    # Strip XML tags like <jats:p> or <jats:sec>
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Query building: title + first author + year (instead of the raw bibliography)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def _strip_marker(ref: str) -> str:
    return re.sub(r"^\s*(\[\d+\]|\(\d+\)|\d+[.)])\s*", "", ref or "").strip()


def parse_year(*texts: str) -> Optional[int]:
    for t in texts:
        m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", t or "")
        if m:
            return int(m.group(1))
    return None


def parse_first_author(in_text: str, reference: str) -> Optional[str]:
    """First author's surname from '(Vaswani et al., 2017)' or the bibliography entry."""
    m = re.match(r"\W*([A-Z][A-Za-z'\u2019\-]{2,})(?:\s+et al\.?|\s+and\s|\s*&|\s*,)", in_text or "")
    if m:
        return m.group(1)
    ref = _strip_marker(reference)
    if not ref:
        return None
    chunk = re.split(r",|;|\band\b|&", ref)[0].strip()
    tokens = [t for t in chunk.split() if t]
    if not tokens or len(tokens) > 4:
        return None
    is_initial = lambda t: len(t.strip(".")) <= 2
    words = [t.strip(".") for t in tokens if not is_initial(t)]
    if not words:
        return None
    # "A. Vaswani" -> last word; "Vaswani, A." -> first chunk is the surname
    return words[-1] if is_initial(tokens[0]) else words[0]


def clean_title(query: str, reference: str = "") -> str:
    title = (query or "").strip().strip('"\u201c\u201d')
    if not title and reference:
        # best effort: the longest sentence-like segment of the reference
        parts = [p.strip() for p in re.split(r"\.\s+|\(\d{4}\)", _strip_marker(reference)) if len(p.strip()) > 12]
        title = max(parts, key=len) if parts else ""
    return re.sub(r"\s+", " ", title)


def _score(title_q: str, author_q: Optional[str], year_q: Optional[int], cand: Dict[str, Any]) -> float:
    a, b = _norm(title_q), _norm(cand.get("title") or "")
    if not a or not b:
        return 0.0
    sim = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) > 12 and (a in b or b in a):
        sim = max(sim, 0.92)
    author = 0.0
    if author_q and cand.get("authors"):
        aq = _norm(author_q)
        surnames = [_norm(n).split(" ")[-1] if _norm(n) else "" for n in cand["authors"]]
        if surnames and surnames[0] == aq:
            author = 1.0
        elif aq in surnames:
            author = 0.5
    year = 0.0
    if year_q and cand.get("year"):
        diff = abs(int(cand["year"]) - year_q)
        year = 1.0 if diff == 0 else 0.6 if diff == 1 else 0.0
    return 0.7 * sim + 0.2 * author + 0.1 * year + (0.03 if cand.get("abstract") else 0.0)


def pick_best(title_q, author_q, year_q, candidates, min_score: float = 0.72):
    """Highest-scoring candidate; ties broken by citation count. None if nothing matches the title."""
    scored = []
    for c in candidates:
        if _norm(title_q) and difflib.SequenceMatcher(None, _norm(title_q), _norm(c.get("title") or "")).ratio() < 0.6 \
                and _norm(title_q) not in _norm(c.get("title") or ""):
            continue
        scored.append((_score(title_q, author_q, year_q, c), c.get("cited_by", 0) or 0, c))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = scored[0]
    if best[0] < min_score:
        return None
    result = {k: v for k, v in best[2].items() if k != "cited_by"}
    return result


def _headers() -> Dict[str, str]:
    return {"User-Agent": f"CiteVerify/1.0 (mailto:{settings.OPENALEX_EMAIL or 'citeverify@example.com'})"}


async def search_openalex(title: str, author: Optional[str], year: Optional[int], client: httpx.AsyncClient):
    """Title-restricted OpenAlex lookup, then local re-ranking by title/author/year."""
    safe_title = _norm(title)
    if not safe_title:
        return None
    params = {
        "filter": f"title.search:{safe_title}",
        "per-page": 25,
        "select": "id,doi,title,display_name,publication_year,authorships,abstract_inverted_index,cited_by_count",
    }
    if settings.OPENALEX_EMAIL:
        params["mailto"] = settings.OPENALEX_EMAIL
    try:
        r = await client.get("https://api.openalex.org/works", params=params, headers=_headers())
        if r.status_code != 200:
            logger.warning(f"OpenAlex status {r.status_code} for title: {title}")
            return None
        cands = []
        for w in r.json().get("results", []):
            doi = w.get("doi")
            cands.append({
                "title": w.get("title") or w.get("display_name") or "",
                "authors": [a.get("author", {}).get("display_name") for a in w.get("authorships", []) if a.get("author", {}).get("display_name")],
                "year": w.get("publication_year"),
                "doi": doi,
                "url": doi or w.get("id"),
                "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
                "cited_by": w.get("cited_by_count", 0),
            })
        return pick_best(title, author, year, cands)
    except Exception as e:
        logger.warning(f"OpenAlex request failed for '{title}': {e}")
        return None


async def search_crossref(title: str, author: Optional[str], year: Optional[int], client: httpx.AsyncClient):
    """Crossref fallback using query.title + query.author, then local re-ranking."""
    params = {
        "query.title": title,
        "rows": 15,
        "select": "DOI,title,author,issued,published-print,published-online,created,abstract,URL,is-referenced-by-count",
    }
    if author:
        params["query.author"] = author
    try:
        r = await client.get("https://api.crossref.org/works", params=params, headers=_headers())
        if r.status_code != 200:
            logger.warning(f"Crossref status {r.status_code} for title: {title}")
            return None
        cands = []
        for item in r.json().get("message", {}).get("items", []):
            raw_title = item.get("title", [])
            authors = []
            for a in item.get("author", []):
                name = f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "")
                if name:
                    authors.append(name)
            y = None
            for f in ("published-print", "published-online", "issued", "created"):
                parts = (item.get(f) or {}).get("date-parts") or [[]]
                if parts[0] and parts[0][0]:
                    y = int(parts[0][0])
                    break
            doi = item.get("DOI")
            cands.append({
                "title": raw_title[0] if raw_title else "",
                "authors": authors,
                "year": y,
                "doi": doi,
                "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
                "abstract": clean_xml_tags(item.get("abstract", "")),
                "cited_by": item.get("is-referenced-by-count", 0),
            })
        return pick_best(title, author, year, cands)
    except Exception as e:
        logger.warning(f"Crossref request failed for '{title}': {e}")
        return None


async def search_semantic_scholar(title: str, author: Optional[str], year: Optional[int], client: httpx.AsyncClient, doi: Optional[str] = None):
    """Abstract fallback #1: Semantic Scholar Graph API (DOI lookup first, then title search)."""
    fields = "title,abstract,year,authors,externalIds,url,citationCount"

    def to_cand(p: Dict[str, Any]) -> Dict[str, Any]:
        ext = p.get("externalIds") or {}
        d = ext.get("DOI")
        return {
            "title": p.get("title") or "",
            "authors": [a.get("name") for a in p.get("authors", []) if a.get("name")],
            "year": p.get("year"),
            "doi": f"https://doi.org/{d}" if d else None,
            "url": (f"https://doi.org/{d}" if d else None) or p.get("url"),
            "abstract": re.sub(r"\s+", " ", p.get("abstract") or "").strip(),
            "cited_by": p.get("citationCount", 0),
        }

    try:
        if doi:
            bare = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
            r = await client.get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{bare}", params={"fields": fields}, headers=_headers())
            if r.status_code == 200:
                cand = to_cand(r.json())
                if cand["abstract"] and _score(title, author, year, cand) >= 0.72:
                    cand.pop("cited_by", None)
                    return cand
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": _norm(title), "limit": 10, "fields": fields},
            headers=_headers(),
        )
        if r.status_code != 200:
            logger.warning(f"Semantic Scholar status {r.status_code} for title: {title}")
            return None
        return pick_best(title, author, year, [to_cand(p) for p in r.json().get("data", [])])
    except Exception as e:
        logger.warning(f"Semantic Scholar request failed for '{title}': {e}")
        return None


async def search_arxiv(title: str, author: Optional[str], year: Optional[int], client: httpx.AsyncClient):
    """Abstract fallback #2: arXiv API (Atom XML). Covers BERT, ResNet and most ML landmarks."""
    safe = _norm(title)
    if not safe:
        return None
    query = f'ti:"{safe}"' + (f" AND au:{_norm(author)}" if author else "")
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    try:
        for q in (query, f'ti:"{safe}"'):
            r = await client.get("https://export.arxiv.org/api/query", params={"search_query": q, "max_results": 8}, headers=_headers())
            if r.status_code != 200:
                logger.warning(f"arXiv status {r.status_code} for title: {title}")
                return None
            cands = []
            for e in ET.fromstring(r.text).findall("a:entry", ns):
                ttl = re.sub(r"\s+", " ", (e.findtext("a:title", "", ns) or "")).strip()
                abs_ = re.sub(r"\s+", " ", (e.findtext("a:summary", "", ns) or "")).strip()
                pub = e.findtext("a:published", "", ns) or ""
                doi = e.findtext("x:doi", None, ns)
                cands.append({
                    "title": ttl,
                    "authors": [n.findtext("a:name", "", ns) for n in e.findall("a:author", ns)],
                    "year": int(pub[:4]) if pub[:4].isdigit() else None,
                    "doi": f"https://doi.org/{doi}" if doi else None,
                    "url": e.findtext("a:id", None, ns),
                    "abstract": abs_,
                    "cited_by": 0,
                })
            best = pick_best(title, author, year, cands)
            if best:
                return best
        return None
    except Exception as e:
        logger.warning(f"arXiv request failed for '{title}': {e}")
        return None


async def search_source(query: str, reference_string: str = "", in_text_citation: str = "") -> Optional[Dict[str, Any]]:
    """
    Finds the cited paper by title + first author + year.
    Order: OpenAlex -> Crossref -> (only if no abstract yet) Semantic Scholar -> arXiv.
    A candidate is only returned if its title actually matches, so a wrong paper's abstract
    is never handed to the verifier.
    """
    title = clean_title(query, reference_string)
    if not title:
        return None
    author = parse_first_author(in_text_citation, reference_string)
    year = parse_year(reference_string, in_text_citation)
    logger.info(f"Source lookup -> title='{title}' author={author} year={year}")

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        oa = await search_openalex(title, author, year, client)
        if oa and oa.get("abstract"):
            return oa
        cr = await search_crossref(title, author, year, client)
        if cr and cr.get("abstract"):
            return cr

        # No abstract from OpenAlex/Crossref: try fallbacks and keep the best metadata we already have.
        meta = oa or cr
        logger.info("No abstract from OpenAlex/Crossref; trying Semantic Scholar and arXiv")
        for finder in (
            lambda: search_semantic_scholar(title, author, year, client, doi=(meta or {}).get("doi")),
            lambda: search_arxiv(title, author, year, client),
        ):
            fb = await finder()
            if fb and fb.get("abstract"):
                if meta:  # keep the published-version DOI/URL when we have one
                    fb["doi"] = meta.get("doi") or fb.get("doi")
                    fb["url"] = meta.get("url") or fb.get("url")
                logger.info(f"Abstract recovered via fallback for '{title}'")
                return fb
        return meta
