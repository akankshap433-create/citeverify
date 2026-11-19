import logging
import re
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


async def search_openalex(query: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Queries the OpenAlex API for works matching the search query.
    Returns parsed work dictionary or None.
    """
    params = {
        "search": query,
        "per-page": 3,
    }
    if settings.OPENALEX_EMAIL:
        params["mailto"] = settings.OPENALEX_EMAIL

    headers = {
        "User-Agent": f"CiteVerify/1.0 (mailto:{settings.OPENALEX_EMAIL or 'citeverify@example.com'})"
    }

    try:
        response = await client.get(
            "https://api.openalex.org/works",
            params=params,
            headers=headers,
        )
        if response.status_code != 200:
            logger.warning(f"OpenAlex returned status code {response.status_code} for query: {query}")
            return None

        data = response.json()
        results = data.get("results", [])
        if not results:
            return None

        # Look for the best result, preferring ones that have an abstract
        best_candidate = None
        for work in results:
            abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
            title = work.get("title") or work.get("display_name") or ""
            
            # Extract authors
            authors = []
            for authorship in work.get("authorships", []):
                author_name = authorship.get("author", {}).get("display_name")
                if author_name:
                    authors.append(author_name)

            year = work.get("publication_year")
            doi = work.get("doi")
            url = doi or work.get("id")

            candidate = {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "url": url,
                "abstract": abstract,
            }

            if abstract:
                return candidate
            if best_candidate is None:
                best_candidate = candidate

        return best_candidate

    except Exception as e:
        logger.warning(f"OpenAlex request failed for query '{query}': {e}")
        return None


async def search_crossref(query: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Fallback query to Crossref API for bibliographic works.
    Returns parsed work dictionary or None.
    """
    params = {
        "query.bibliographic": query,
        "rows": 3,
    }
    headers = {
        "User-Agent": f"CiteVerify/1.0 (mailto:{settings.OPENALEX_EMAIL or 'citeverify@example.com'})"
    }

    try:
        response = await client.get(
            "https://api.crossref.org/works",
            params=params,
            headers=headers,
        )
        if response.status_code != 200:
            logger.warning(f"Crossref returned status code {response.status_code} for query: {query}")
            return None

        data = response.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            return None

        best_candidate = None
        for item in items:
            raw_title = item.get("title", [])
            title = raw_title[0] if raw_title else ""

            # Extract authors
            authors = []
            for a in item.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                full_name = f"{given} {family}".strip()
                if not full_name and a.get("name"):
                    full_name = a.get("name")
                if full_name:
                    authors.append(full_name)

            # Extract year
            year = None
            for date_field in ("published-print", "published-online", "issued", "created"):
                date_data = item.get(date_field)
                if date_data and "date-parts" in date_data and date_data["date-parts"]:
                    parts = date_data["date-parts"][0]
                    if parts and parts[0]:
                        try:
                            year = int(parts[0])
                            break
                        except (ValueError, TypeError):
                            pass

            doi = item.get("DOI")
            url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
            abstract = clean_xml_tags(item.get("abstract", ""))

            candidate = {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "url": url,
                "abstract": abstract,
            }

            if abstract:
                return candidate
            if best_candidate is None:
                best_candidate = candidate

        return best_candidate

    except Exception as e:
        logger.warning(f"Crossref request failed for query '{query}': {e}")
        return None


async def search_source(query: str) -> Optional[Dict[str, Any]]:
    """
    Searches for academic source metadata and abstract.
    Tries OpenAlex first; if not found or missing abstract, attempts Crossref as fallback.
    Uses async httpx with a 10-second timeout.
    """
    if not query or not query.strip():
        return None

    clean_query = query.strip()
    timeout = httpx.Timeout(10.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        # 1. Primary: OpenAlex
        openalex_result = await search_openalex(clean_query, client)
        if openalex_result and openalex_result.get("abstract"):
            return openalex_result

        # 2. Fallback: Crossref
        crossref_result = await search_crossref(clean_query, client)
        if crossref_result and crossref_result.get("abstract"):
            return crossref_result

        # If OpenAlex returned metadata (even if abstract is missing), use it if Crossref also has no abstract
        if openalex_result:
            return openalex_result

        # Otherwise return Crossref metadata or None
        return crossref_result
