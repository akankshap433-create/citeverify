"""Pure helpers for the replacement-citation finder (no network, no AI)."""
import math
import re
from typing import Any, Dict, List, Optional

_STOP = set("a an and are as at be been but by for from has have in into is it its of on or that the their these this to was were which with while within than then also can may more most such using used use show shows showed shown study studies paper results result".split())


def fallback_query(claim: str, max_words: int = 9) -> str:
    """Keyword query used only if Gemini is unavailable."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", claim) if w.lower() not in _STOP]
    seen, out = set(), []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return " ".join(out[:max_words])


def _apa_author(name: str) -> str:
    parts = name.replace(".", ". ").split()
    if len(parts) <= 1:
        return name.strip()
    initials = " ".join(p[0].upper() + "." for p in parts[:-1] if p and p[0].isalpha())
    return f"{parts[-1]}, {initials}".strip().rstrip(",")


def doi_url(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    return doi if doi.lower().startswith("http") else f"https://doi.org/{doi}"


def apa_citation(c: Dict[str, Any]) -> str:
    """APA 7 reference built from real metadata (never invented by the model)."""
    authors = [_apa_author(a) for a in c.get("authors", []) if a]
    if len(authors) > 20:
        authors = authors[:19] + ["...", authors[-1]]
        who = ", ".join(authors[:-2]) + ", " + authors[-2] + " " + authors[-1]
    elif len(authors) > 2:
        who = ", ".join(authors[:-1]) + ", & " + authors[-1]
    elif len(authors) == 2:
        who = f"{authors[0]} & {authors[1]}"
    else:
        who = authors[0] if authors else ""
    year = f"({c['year']})" if c.get("year") else "(n.d.)"
    title = re.sub(r"\s+", " ", c.get("title", "")).strip()
    if title and title[-1] not in ".?!":
        title += "."
    link = c.get("doi") or c.get("url") or ""
    head = f"{who} {year}." if who else f"{title} {year}."
    body = f" {title}" if who else ""
    return f"{head}{body} {link}".strip()


def rank_candidates(cands: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """Keep search relevance order, nudged by citation count; drop duplicates and abstract-less records."""
    seen, scored = set(), []
    for i, c in enumerate(cands):
        key = re.sub(r"[^a-z0-9]", "", (c.get("title") or "").lower())
        if not key or key in seen or not c.get("abstract") or not (c.get("doi") or c.get("url")):
            continue
        seen.add(key)
        scored.append((-i + 1.5 * math.log10((c.get("cited_by") or 0) + 1), c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]
