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
        f"_{DISCLAIMER}_",
        "",
        "_Report produced by CiteVerify Autonomous Verification Engine (2026)._",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF report (ReportLab)
# ---------------------------------------------------------------------------
import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = "Automated verification indicator \u2014 intended to assist human review, not serve as final academic judgment."


def _source_href(doi, url):
    """Best clickable link for a source: paper URL, else DOI resolved through doi.org."""
    if url:
        return str(url)
    if doi:
        d = str(doi)
        return d if d.lower().startswith("http") else f"https://doi.org/{d}"
    return None


_VERDICT_COLORS = {
    "Supported": "#10B981",
    "Partially Supported": "#65A30D",
    "Unsupported": "#F59E0B",
    "Contradictory": "#DC2626",
    "Potentially Outdated": "#7C3AED",
    "Unable to Verify": "#64748B",
}
_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def _register_fonts():
    """Use a Unicode TTF when available (Greek letters, accents); fall back to Helvetica."""
    for reg, bold in _FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("CV", reg))
                pdfmetrics.registerFont(TTFont("CV-B", bold))
                pdfmetrics.registerFontFamily("CV", normal="CV", bold="CV-B", italic="CV", boldItalic="CV-B")
                return "CV", "CV-B", True
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", False


def _build_pdf(doc: Dict[str, Any], claims: List[Dict[str, Any]], document_id: str) -> bytes:
    font, bold, unicode_ok = _register_fonts()

    def t(x) -> str:
        x = "" if x is None else str(x)
        if not unicode_ok:
            x = x.encode("cp1252", "replace").decode("cp1252")
        return escape(x)

    def link_markup(c) -> str:
        href = _source_href(c.get("source_doi"), c.get("source_url"))
        if not href:
            return "No source found"
        return f'<a href="{escape(href, {chr(34): "&quot;"})}" color="#2563EB"><u>{t(href)}</u></a>'

    ink, slate = colors.HexColor("#0F172A"), colors.HexColor("#475569")
    base = ParagraphStyle("base", fontName=font, fontSize=9.5, leading=13.5, textColor=ink, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=base, fontSize=8.5, leading=12, textColor=slate)
    h1 = ParagraphStyle("h1", parent=base, fontName=bold, fontSize=20, leading=24, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=base, fontName=bold, fontSize=13, leading=17, spaceBefore=10, spaceAfter=6)
    quote = ParagraphStyle("quote", parent=base, leftIndent=10, textColor=colors.HexColor("#334155"), backColor=colors.HexColor("#F1F5F9"), borderPadding=(5, 6, 5, 8))

    total = len(claims)
    counts = {k: 0 for k in _VERDICT_COLORS}
    for c in claims:
        counts[c.get("verdict") if c.get("verdict") in counts else "Unable to Verify"] += 1
    rate = (counts["Supported"] + counts["Partially Supported"]) / total * 100 if total else 0.0

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                            title="CiteVerify Verification Report", author="CiteVerify")
    story = [
        Paragraph("CiteVerify Verification Report", h1),
        Paragraph(f"{t(doc.get('filename', 'Unknown document'))}", small),
        Paragraph(f"Document ID {t(document_id)} &nbsp;|&nbsp; Uploaded {t(doc.get('created_at', 'N/A'))} &nbsp;|&nbsp; Status {t(str(doc.get('status', '')).replace('_', ' '))}", small),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1")),
        Spacer(1, 6),
        Paragraph(f"<i>{t(DISCLAIMER)}</i>", ParagraphStyle("disc", parent=small, backColor=colors.HexColor("#F1F5F9"), borderPadding=(5, 6, 5, 6), leading=11.5)),
        Paragraph("Summary", h2),
        Paragraph(f"<b>{total}</b> claims analyzed. Support rate (Supported + Partially Supported): <b>{rate:.1f}%</b>.", base),
        Spacer(1, 6),
    ]

    rows = [[Paragraph("<b>Verdict</b>", base), Paragraph("<b>Count</b>", base), Paragraph("<b>Share</b>", base)]]
    for verdict, n in counts.items():
        rows.append([Paragraph(f'<font color="{_VERDICT_COLORS[verdict]}"><b>{verdict}</b></font>', base), str(n), f"{(n / total * 100) if total else 0:.1f}%"])
    tbl = Table(rows, colWidths=[80 * mm, 30 * mm, 30 * mm], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [tbl, Paragraph("Detailed claims", h2)]

    if not claims:
        story.append(Paragraph("No cited claims were extracted or verified for this document.", base))
    for i, c in enumerate(claims, 1):
        verdict = c.get("verdict") or "Unable to Verify"
        color = _VERDICT_COLORS.get(verdict, "#64748B")
        conf = int((c.get("confidence") or 0) * 100)
        authors = c.get("source_authors")
        authors = ", ".join(authors) if isinstance(authors, list) else (authors or "N/A")
        block = [
            Paragraph(f'<b>Claim {i}</b> &nbsp; <font color="{color}"><b>{t(verdict)}</b></font> &nbsp; <font color="#64748B">{conf}% confidence</font>', base),
            Spacer(1, 3),
            Paragraph(t(c.get("claim_text")), base),
            Paragraph(f"<b>Cited as:</b> {t(c.get('in_text_citation'))}", small),
            Paragraph(f"<b>Reference:</b> {t(c.get('reference_string'))}", small),
            Spacer(1, 3),
            Paragraph(f"<b>Explanation.</b> {t(c.get('explanation') or 'No explanation provided.')}", base),
            Spacer(1, 3),
        ]
        if c.get("evidence_passage"):
            block += [Paragraph(f"<b>Evidence from source abstract</b>", small), Spacer(1, 2), Paragraph(f"\u201c{t(c['evidence_passage'])}\u201d", quote), Spacer(1, 4)]
        else:
            block.append(Paragraph("<i>No direct evidence passage retrieved from the source abstract.</i>", small))
        block += [
            Paragraph(f"<b>Matched source:</b> {t(c.get('source_title') or 'N/A')} ({t(c.get('source_year') or 'N/A')})", small),
            Paragraph(f"<b>Authors:</b> {t(authors)}", small),
            Paragraph(f"<b>Source link:</b> {link_markup(c)}", small),
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#E2E8F0")),
            Spacer(1, 6),
        ]
        story.append(KeepTogether(block))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(slate)
        canvas.setFont(font, 7)
        canvas.drawCentredString(A4[0] / 2, 12.5 * mm, DISCLAIMER if unicode_ok else DISCLAIMER.encode("cp1252", "replace").decode("cp1252"))
        canvas.setFont(font, 8)
        canvas.drawString(18 * mm, 8 * mm, "Produced by CiteVerify")
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


async def generate_pdf_report(document_id: str) -> bytes:
    """Builds the verification report as a formatted PDF and returns its bytes."""
    doc = await get_document(document_id)
    if not doc:
        raise ValueError(f"Document with ID {document_id} not found.")
    claims = await get_claims_for_document(document_id)
    return _build_pdf(doc, claims, document_id)
