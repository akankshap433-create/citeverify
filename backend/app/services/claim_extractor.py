import logging
from typing import Optional
from google import genai
from google.genai import types

from app.config import settings
from app.schemas import ExtractedClaimsResponse

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are CiteVerify's scientific citation analyzer.
Your task is to analyze scientific or academic text, identify specific scientific or factual claims that have an explicit in-text citation, map each citation to its corresponding entry in the bibliography/references section, and formulate a clean search query to locate the cited paper.

Rules:
1. Extract at most 10 explicit scientific or empirical claims that are directly supported by an in-text citation.
2. For each claim:
   - claim_text: The factual or scientific claim made in the text.
   - in_text_citation: The exact in-text citation marker as it appears in the text (e.g. "[1]", "(Vaswani et al., 2017)", "(Smith, 2020)").
   - reference_string: The full citation entry from the References / Bibliography section matching that citation marker.
   - search_query: The clean title of the cited paper, optimized for academic search (e.g. OpenAlex / Crossref). Do not include author names, journal volume, or publication year in search_query if the paper title is identifiable.
3. STRICT CITATION INTEGRITY: NEVER invent or hallucinate citations or references. Only extract claims that have an actual in-text citation present in the document.
4. If no cited claims are found, return an empty list of claims.
"""


def get_genai_client() -> genai.Client:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in environment or .env file.")
    return genai.Client(api_key=api_key)


async def extract_claims(paper_text: str) -> ExtractedClaimsResponse:
    """
    Extracts up to 10 cited scientific claims from paper text using Gemini 2.5 Flash.
    Maps each in-text citation to its full reference entry and generates a clean search query.
    """
    if not paper_text or not paper_text.strip():
        return ExtractedClaimsResponse(claims=[])

    client = get_genai_client()

    # If text is exceptionally large, preserve body and bibliography at the end
    processed_text = paper_text
    if len(paper_text) > 150000:
        processed_text = paper_text[:100000] + "\n\n[... content omitted ...]\n\n" + paper_text[-50000:]

    prompt = f"""Analyze the following paper text and extract up to 10 cited scientific claims.
Map each citation marker to its corresponding reference entry, and provide a clean paper title search query.

Paper text:
\"\"\"
{processed_text}
\"\"\"
"""

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExtractedClaimsResponse,
                temperature=0.1,
            ),
        )

        if hasattr(response, "parsed") and isinstance(response.parsed, ExtractedClaimsResponse):
            return response.parsed
        elif hasattr(response, "parsed") and response.parsed is not None:
            if isinstance(response.parsed, dict):
                return ExtractedClaimsResponse.model_validate(response.parsed)
            return response.parsed
        elif response.text:
            return ExtractedClaimsResponse.model_validate_json(response.text)

        return ExtractedClaimsResponse(claims=[])
    except Exception as e:
        logger.error(f"Error during claim extraction: {e}")
        raise
