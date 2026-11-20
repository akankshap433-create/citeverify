import logging
import re
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

from app.config import settings
from app.schemas import ExtractedClaim, VerificationJudgment

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_INSTRUCTION = """You are CiteVerify, an elite scientific citation verifier and academic fact-checker.
The current year is 2026.

Your objective is to evaluate whether an extracted scientific claim is factually and contextually supported by the abstract of the cited paper.

Available Verdicts (VerdictLiteral):
- "Supported": The retrieved abstract directly, accurately, and unambiguously supports the claim.
- "Partially Supported": The retrieved abstract provides partial support, but the claim oversimplifies, exaggerates, or includes assertions not confirmed by the abstract.
- "Unsupported": The abstract discusses related topics, but does not provide evidence supporting the specific claim.
- "Contradictory": The abstract directly contradicts, disproves, or opposes the claim.
- "Potentially Outdated": ONLY for claims that make a CURRENT or state-of-the-art assertion (e.g. "X is the best / state-of-the-art / currently the leading approach / still the standard") and rely on an old source (published before 2015) in a fast-moving field where that assertion has likely been superseded. The claim must be about the present state of the field, not about what the paper did.

HISTORICAL vs. CURRENT CLAIMS (critical):
- A claim that accurately describes what a paper proposed, introduced, trained, demonstrated, or found is a HISTORICAL claim. Judge it only on whether the abstract supports it. Publication age is irrelevant to the verdict.
  Examples that must be "Supported" when the abstract matches: "Vaswani et al. (2017) proposed the Transformer", "Krizhevsky et al. (2012) trained a deep CNN (AlexNet) on ImageNet", "Devlin et al. (2019) introduced BERT".
- Foundational and landmark papers must NEVER be marked "Potentially Outdated" for a historical claim just because they are older.
- Do not use "Potentially Outdated" unless the claim itself asserts something about the present ("currently", "state-of-the-art", "best", "still", "remains", "outperforms all") and the source is too old to back that up. When unsure, choose "Supported", "Partially Supported" or "Unsupported" based on the abstract alone.
- "Unable to Verify": The retrieved abstract lacks sufficient scientific detail or context to evaluate the claim.

STRICT GROUNDING REQUIREMENT:
- "evidence_passage" MUST be an exact, verbatim quotation copied directly from the retrieved abstract.
- Do NOT paraphrase, alter, or construct words.
- If no sentence or passage in the abstract directly supports or addresses the claim, or if the verdict is "Unable to Verify", "evidence_passage" MUST be an empty string ("").

CONFIDENCE:
- A float between 0.0 and 1.0 reflecting your confidence in the verdict.
"""


CURRENT_CLAIM_RE = re.compile(
    r"state[- ]of[- ]the[- ]art|\bsota\b|\bcurrent(ly)?\b|\bstill\b|\bremains?\b|\bbest\b|\bleading\b|"
    r"\bmost (accurate|effective|powerful|widely)\b|outperforms? (all|every|existing)|\bto date\b|\bnowadays\b|\btoday\b",
    re.IGNORECASE,
)


def get_genai_client() -> genai.Client:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in environment or .env file.")
    return genai.Client(api_key=api_key)


def enforce_verbatim_grounding(evidence: str, abstract: str) -> str:
    """
    Validates that evidence_passage is a verbatim quote from the abstract.
    If whitespace/formatting differs slightly, finds and returns the exact substring from the abstract.
    If not found in the abstract, returns an empty string to maintain strict grounding.
    """
    if not evidence or not abstract:
        return ""

    evidence_clean = evidence.strip().strip('"').strip("'")
    if not evidence_clean:
        return ""

    # Check direct substring
    if evidence_clean in abstract:
        return evidence_clean

    # Case-insensitive substring check
    idx = abstract.lower().find(evidence_clean.lower())
    if idx != -1:
        return abstract[idx : idx + len(evidence_clean)]

    # Normalized whitespace comparison
    norm_evidence = " ".join(evidence_clean.split())
    # Try finding sentences or clauses in the abstract
    for line in abstract.split("."):
        line_clean = line.strip()
        if norm_evidence.lower() in line_clean.lower() or line_clean.lower() in norm_evidence.lower():
            if len(line_clean) > 20:
                return line_clean

    logger.warning("Evidence passage was not found verbatim in retrieved abstract. Stripping hallucinated quote.")
    return ""


async def verify_claim(
    claim: ExtractedClaim,
    source_data: Optional[Dict[str, Any]],
) -> VerificationJudgment:
    """
    Verifies a single extracted claim against retrieved source metadata and abstract.
    Enforces strict grounding and the 2026 temporal reference rule.
    """
    # Contract requirement: If no source or abstract is retrieved
    if not source_data or not source_data.get("abstract") or not source_data.get("abstract", "").strip():
        return VerificationJudgment(
            verdict="Unable to Verify",
            confidence=0.0,
            explanation="Could not retrieve source abstract from OpenAlex/Crossref.",
            evidence_passage="",
        )

    abstract = source_data.get("abstract", "").strip()
    title = source_data.get("title", "Unknown Title")
    year = source_data.get("year", "Unknown Year")
    authors = ", ".join(source_data.get("authors", [])) or "Unknown Authors"

    prompt = f"""Evaluate the following scientific claim against the retrieved paper abstract:

[CURRENT YEAR]: 2026

[CLAIM TO VERIFY]:
\"{claim.claim_text}\"

[IN-TEXT CITATION IN PAPER]:
\"{claim.in_text_citation}\"

[FULL BIBLIOGRAPHY ENTRY]:
\"{claim.reference_string}\"

[RETRIEVED SOURCE METADATA]:
Title: {title}
Authors: {authors}
Year: {year}

[RETRIEVED ABSTRACT]:
\"\"\"
{abstract}
\"\"\"

Analyze whether the abstract supports, partially supports, contradicts, or fails to support the claim. First decide if the claim is HISTORICAL (describes what the cited paper proposed or found) or CURRENT (asserts today's state of the art). Use \"Potentially Outdated\" only for CURRENT claims backed by a pre-2015 source; historical claims that the abstract supports are \"Supported\" regardless of the paper's age.
Extract a verbatim quote for evidence_passage, or return an empty string if none exists.
"""

    client = get_genai_client()

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=VERIFIER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=VerificationJudgment,
                temperature=0.1,
            ),
        )

        judgment: Optional[VerificationJudgment] = None
        if hasattr(response, "parsed") and isinstance(response.parsed, VerificationJudgment):
            judgment = response.parsed
        elif hasattr(response, "parsed") and response.parsed is not None:
            if isinstance(response.parsed, dict):
                judgment = VerificationJudgment.model_validate(response.parsed)
            else:
                judgment = response.parsed
        elif response.text:
            judgment = VerificationJudgment.model_validate_json(response.text)

        if judgment is None:
            return VerificationJudgment(
                verdict="Unable to Verify",
                confidence=0.0,
                explanation="Failed to parse verification response from model.",
                evidence_passage="",
            )

        # Enforce strict grounding for evidence_passage
        clean_evidence = enforce_verbatim_grounding(judgment.evidence_passage, abstract)
        
        verdict = judgment.verdict
        if verdict == "Potentially Outdated" and clean_evidence and not CURRENT_CLAIM_RE.search(claim.claim_text or ""):
            # Historical claim with a verbatim supporting passage: age alone must not downgrade it.
            logger.info("Downgrading 'Potentially Outdated' to 'Supported' for a historical claim.")
            verdict = "Supported"

        return VerificationJudgment(
            verdict=verdict,
            confidence=round(float(judgment.confidence), 2),
            explanation=judgment.explanation,
            evidence_passage=clean_evidence,
        )

    except Exception as e:
        logger.error(f"Error during claim verification: {e}")
        return VerificationJudgment(
            verdict="Unable to Verify",
            confidence=0.0,
            explanation=f"Verification encountered an error: {str(e)}",
            evidence_passage="",
        )
