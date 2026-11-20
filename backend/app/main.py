import logging
import uuid
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.schemas import (
    DocumentUploadResponse,
    DocumentAnalyzeResponse,
    DocumentResultsResponse,
    ClaimSummary,
    ClaimResult,
    DocumentHistoryItem,
    SuggestCitationsRequest,
    SuggestCitationsResponse,
)
from app.services.pdf_parser import extract_text_from_pdf
from app.services.claim_extractor import extract_claims
from app.services.research_api import search_source
from app.services.verifier import verify_claim
from app.services.suggester import suggest_citations
from app.services.report_gen import generate_markdown_report, generate_pdf_report
from app.services.db import (
    insert_document,
    update_document_status,
    get_document,
    get_recent_documents,
    insert_claims,
    get_claims_for_document,
    get_current_iso_time,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citeverify")

app = FastAPI(
    title="CiteVerify API",
    description="Automated Academic Citation & Claim Verification Backend",
    version="1.0.0",
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compute_summary(claims: List[Dict[str, Any]]) -> ClaimSummary:
    """Computes categorical counts for claim verification verdicts."""
    summary_counts = {
        "total_claims": len(claims),
        "supported": 0,
        "partially_supported": 0,
        "unsupported": 0,
        "contradictory": 0,
        "potentially_outdated": 0,
        "unable_to_verify": 0,
    }

    verdict_key_map = {
        "Supported": "supported",
        "Partially Supported": "partially_supported",
        "Unsupported": "unsupported",
        "Contradictory": "contradictory",
        "Potentially Outdated": "potentially_outdated",
        "Unable to Verify": "unable_to_verify",
    }

    for c in claims:
        verdict = c.get("verdict", "Unable to Verify")
        key = verdict_key_map.get(verdict, "unable_to_verify")
        summary_counts[key] += 1

    return ClaimSummary(**summary_counts)


async def run_verification_pipeline(document_id: str) -> None:
    """
    Background pipeline executing the 4-phase verification process:
    1. extracting_claims
    2. retrieving_sources
    3. verifying_claims
    4. completed (or failed)
    """
    logger.info(f"Starting verification pipeline for document: {document_id}")
    try:
        # Phase 1: Extracting claims
        await update_document_status(document_id, "extracting_claims")
        doc = await get_document(document_id)
        if not doc:
            logger.error(f"Document {document_id} not found in database.")
            return

        extracted_text = doc.get("extracted_text", "")
        if not extracted_text.strip():
            await update_document_status(
                document_id,
                "failed",
                error_message="Document contains no readable text content.",
            )
            return

        claims_response = await extract_claims(extracted_text)
        claims = claims_response.claims

        if not claims:
            logger.info(f"No cited scientific claims extracted for document: {document_id}")
            await update_document_status(document_id, "completed")
            return

        # Phase 2: Retrieving sources
        await update_document_status(document_id, "retrieving_sources")
        sources = []
        for claim in claims:
            source_data = await search_source(
                claim.search_query,
                reference_string=claim.reference_string,
                in_text_citation=claim.in_text_citation,
            )
            sources.append(source_data)

        # Phase 3: Verifying claims
        await update_document_status(document_id, "verifying_claims")
        verified_claim_records = []
        for claim, source in zip(claims, sources):
            judgment = await verify_claim(claim, source)

            record = {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "claim_text": claim.claim_text,
                "in_text_citation": claim.in_text_citation,
                "reference_string": claim.reference_string,
                "search_query": claim.search_query,
                "verdict": judgment.verdict,
                "confidence": judgment.confidence,
                "explanation": judgment.explanation,
                "evidence_passage": judgment.evidence_passage,
                "source_title": source.get("title") if source else None,
                "source_authors": source.get("authors") if source else None,
                "source_year": source.get("year") if source else None,
                "source_doi": source.get("doi") if source else None,
                "source_url": source.get("url") if source else None,
                "source_abstract": source.get("abstract") if source else None,
                "created_at": get_current_iso_time(),
            }
            verified_claim_records.append(record)

        # Save all verified claims
        await insert_claims(verified_claim_records)

        # Phase 4: Completed
        await update_document_status(document_id, "completed")
        logger.info(f"Verification pipeline completed successfully for document: {document_id}")

    except Exception as e:
        logger.exception(f"Verification pipeline failed for document {document_id}: {e}")
        await update_document_status(document_id, "failed", error_message=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "CiteVerify API",
        "timestamp": get_current_iso_time(),
    }


@app.post("/api/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts PDF file, extracts text via PyMuPDF, saves record in documents,
    and returns {document_id, filename, status: "uploaded"}.
    """
    if not file.filename.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        content = await file.read()
        extracted_text = extract_text_from_pdf(content)
    except Exception as e:
        logger.error(f"Failed to parse PDF {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")

    document_id = str(uuid.uuid4())
    await insert_document(
        doc_id=document_id,
        filename=file.filename,
        extracted_text=extracted_text,
        status="uploaded",
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="uploaded",
    )


@app.post("/api/analyze/{document_id}", response_model=DocumentAnalyzeResponse)
async def analyze_document(document_id: str, background_tasks: BackgroundTasks):
    """
    Kicks off the verification pipeline in BackgroundTasks.
    Updates status: extracting_claims -> retrieving_sources -> verifying_claims -> completed/failed.
    """
    doc = await get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    background_tasks.add_task(run_verification_pipeline, document_id)

    return DocumentAnalyzeResponse(
        document_id=document_id,
        status="extracting_claims",
        message="Verification pipeline started in background.",
    )


@app.get("/api/results/{document_id}", response_model=DocumentResultsResponse)
async def get_results(document_id: str):
    """
    Returns full analysis results, progress status, categorical summary metrics,
    and verified claims for the given document_id.
    """
    doc = await get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    raw_claims = await get_claims_for_document(document_id)
    summary = compute_summary(raw_claims)

    claims_list = [ClaimResult(**c) for c in raw_claims]

    return DocumentResultsResponse(
        document_id=document_id,
        filename=doc.get("filename", ""),
        status=doc.get("status", "unknown"),
        error_message=doc.get("error_message"),
        created_at=doc.get("created_at"),
        summary=summary,
        claims=claims_list,
    )


@app.get("/api/history", response_model=List[DocumentHistoryItem])
async def get_history():
    """
    Returns recent documents ordered by created_at DESC.
    """
    docs = await get_recent_documents(limit=50)
    history_items = []
    for d in docs:
        doc_id = d.get("id") or d.get("document_id", "")
        raw_claims = await get_claims_for_document(doc_id)
        history_items.append(
            DocumentHistoryItem(
                document_id=doc_id,
                filename=d.get("filename", "Untitled"),
                status=d.get("status", "unknown"),
                error_message=d.get("error_message"),
                created_at=d.get("created_at"),
                total_claims=len(raw_claims),
            )
        )
    return history_items


@app.post("/api/suggest-citations", response_model=SuggestCitationsResponse)
async def suggest_citations_endpoint(req: SuggestCitationsRequest):
    """Finds 2-3 real papers that could replace a weak citation, with a one-line reason and an APA reference."""
    try:
        return await suggest_citations(req.claim_text)
    except Exception as e:
        logger.exception(f"Suggest citations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Could not find replacement sources: {str(e)}")


@app.get("/api/report/{document_id}")
async def download_report(document_id: str, format: str = "pdf"):
    """
    Returns the verification report as a formatted PDF (default).
    Pass ?format=md to get the Markdown version instead.
    """
    try:
        doc = await get_document(document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")
        clean_name = (doc.get("filename") or "document").rsplit(".", 1)[0]
        base_name = f"citeverify_report_{clean_name}_{document_id[:8]}"

        if format.lower() == "md":
            content = (await generate_markdown_report(document_id)).encode("utf-8")
            media_type, ext = "text/markdown", "md"
        else:
            content = await generate_pdf_report(document_id)
            media_type, ext = "application/pdf", "pdf"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{base_name}.{ext}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate report for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
