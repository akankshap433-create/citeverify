from typing import List, Dict, Any
from app.services.db import get_document, get_claims_for_document


VERDICT_EMOJIS = {
    "Supported": "Supported",
    "Partially Supported": "Partially Supported",
    "Unsupported": "Unsupported",
    "Contradictory": "Contradictory",
    "Potentially Outdated": "Potentially Outdated",
    "Unable to Verify": "Unable to Verify",
}


async def generate_markdown_report(document_id: str) -> str:
    """
    Generates a clean, downloadable Markdown verification report for a document.
    """
    doc = await get_document(document_id)
    if not doc:
        raise ValueError(f"Document with ID {document_id} not found.")

    claims: List[Dict[str, Any]] = await get_claims_for_document(document_id)

    filename = doc.get("filename", "Unknown Document")
    status = doc.get("status", "Unknown")
    created_at = doc.get("created_at", "N/A")

    # Calculate summary metrics
    summary = {
        "Supported": 0,
        "Partially Supported": 0,
        "Unsupported": 0,
        "Contradictory": 0,
        "Potentially Outdated": 0,
        "Unable to Verify": 0,
    }

    for c in claims:
        v = c.get("verdict", "Unable to Verify")
        if v in summary:
            summary[v] += 1
        else:
            summary["Unable to Verify"] += 1

    total_claims = len(claims)
    verified_supported = summary["Supported"] + summary["Partially Supported"]
    support_rate = (verified_supported / total_claims * 100) if total_claims > 0 else 0.0

    lines = [
        f"# CiteVerify Academic Verification Report",
        "",
        f"**Document**: `{filename}`  ",
        f"**Document ID**: `{document_id}`  ",
        f"**Date Generated**: `{created_at}`  ",
        f"**Analysis Status**: `{status.upper()}`  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Total Claims Analyzed**: {total_claims}",
        f"- **Support Rate (Supported + Partially Supported)**: {support_rate:.1f}%",
        "",
        "| Verdict Category | Count | Percentage |",
        "| :--- | :---: | :---: |",
        f"| Supported | {summary['Supported']} | {(summary['Supported'] / total_claims * 100) if total_claims else 0:.1f}% |",
        f"| Partially Supported | {summary['Partially Supported']} | {(summary['Partially Supported'] / total_claims * 100) if total_claims else 0:.1f}% |",
        f"| Unsupported | {summary['Unsupported']} | {(summary['Unsupported'] / total_claims * 100) if total_claims else 0:.1f}% |",
        f"| Contradictory | {summary['Contradictory']} | {(summary['Contradictory'] / total_claims * 100) if total_claims else 0:.1f}% |",
        f"| Potentially Outdated (pre-2015) | {summary['Potentially Outdated']} | {(summary['Potentially Outdated'] / total_claims * 100) if total_claims else 0:.1f}% |",
        f"| Unable to Verify | {summary['Unable to Verify']} | {(summary['Unable to Verify'] / total_claims * 100) if total_claims else 0:.1f}% |",
        "",
        "---",
        "",
        "## Detailed Verification Claims",
        "",
    ]

    if not claims:
        lines.append("*No cited claims were extracted or verified for this document.*")
    else:
        for idx, claim in enumerate(claims, 1):
            verdict = claim.get("verdict", "Unable to Verify")
            confidence = claim.get("confidence", 0.0)
            conf_percent = int(confidence * 100) if isinstance(confidence, (int, float)) else 0
            claim_text = claim.get("claim_text", "")
            in_text = claim.get("in_text_citation", "")
            ref_str = claim.get("reference_string", "")
            explanation = claim.get("explanation", "No explanation provided.")
            evidence = claim.get("evidence_passage", "")

            src_title = claim.get("source_title") or "N/A"
            src_year = claim.get("source_year") or "N/A"
            src_authors = claim.get("source_authors")
            if isinstance(src_authors, list):
                src_authors_str = ", ".join(src_authors) or "N/A"
            else:
                src_authors_str = str(src_authors) if src_authors else "N/A"
            src_doi = claim.get("source_doi") or "N/A"
            src_url = claim.get("source_url") or ""

            lines.extend([
                f"### Claim {idx}: [{verdict}] ({conf_percent}% Confidence)",
                "",
                f"> **Claim**: \"{claim_text}\"",
                "",
                f"- **In-Text Citation**: `{in_text}`",
                f"- **Bibliography Reference**: {ref_str}",
                f"- **Verdict**: **{verdict}**",
                f"- **Explanation**: {explanation}",
                "",
            ])

            if evidence:
                lines.extend([
                    "**Verbatim Evidence Passage from Source**:",
                    f"> \"{evidence}\"",
                    "",
                ])
            else:
                lines.extend([
                    "**Evidence Passage**: *No direct supporting passage retrieved from source abstract.*",
                    "",
                ])

            doi_display = f"[{src_doi}]({src_url})" if src_url and src_doi != "N/A" else src_doi
            lines.extend([
                "**Retrieved Source Information**:",
                f"- **Title**: {src_title}",
                f"- **Authors**: {src_authors_str}",
                f"- **Year**: {src_year}",
                f"- **DOI / Link**: {doi_display}",
                "",
                "---",
                "",
            ])

    lines.extend([
        "",
        "_Report produced by CiteVerify Autonomous Verification Engine (2026)._",
    ])

    return "\n".join(lines)
