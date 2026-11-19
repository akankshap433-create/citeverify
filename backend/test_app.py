import io
import asyncio
import pymupdf
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas import (
    ExtractedClaimsResponse,
    ExtractedClaim,
    VerificationJudgment,
)
from app.services.pdf_parser import extract_text_from_pdf
from app.services.research_api import reconstruct_abstract, clean_xml_tags
from app.services.verifier import verify_claim, enforce_verbatim_grounding
from app.services.db import (
    insert_document,
    get_document,
    update_document_status,
    insert_claims,
    get_claims_for_document,
)

client = TestClient(app)


def create_sample_pdf() -> bytes:
    """Helper to generate valid PDF bytes in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    text = (
        "Recent experiments demonstrate that Transformers outperform RNNs on machine translation [1].\n\n"
        "References\n"
        "[1] Vaswani et al., Attention is All You Need, NeurIPS 2017."
    )
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    print("✓ Health endpoint passed")


def test_pdf_parser():
    pdf_bytes = create_sample_pdf()
    text = extract_text_from_pdf(pdf_bytes)
    assert "Transformers outperform RNNs" in text
    assert "Vaswani et al." in text
    print("✓ PDF parser test passed")


def test_research_api_helpers():
    # Test reconstruct_abstract
    inverted_index = {
        "Transformers": [0],
        "are": [1],
        "effective": [2],
        "models": [3],
    }
    abstract = reconstruct_abstract(inverted_index)
    assert abstract == "Transformers are effective models"

    # Test empty / None
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""

    # Test clean_xml_tags
    raw_xml = "<jats:p>This is a <jats:bold>test</jats:bold> abstract.</jats:p>"
    clean = clean_xml_tags(raw_xml)
    assert clean == "This is a test abstract."
    print("✓ Research API helpers test passed")


def test_verifier_no_abstract():
    claim = ExtractedClaim(
        claim_text="Transformers outperform RNNs",
        in_text_citation="[1]",
        reference_string="Vaswani et al., 2017",
        search_query="Attention is All You Need",
    )
    # When source_data is None or abstract is empty
    loop = asyncio.new_event_loop()
    judgment = loop.run_until_complete(verify_claim(claim, None))
    loop.close()

    assert judgment.verdict == "Unable to Verify"
    assert judgment.confidence == 0.0
    assert judgment.explanation == "Could not retrieve source abstract from OpenAlex/Crossref."
    assert judgment.evidence_passage == ""
    print("✓ Verifier no-abstract fallback test passed")


def test_enforce_verbatim_grounding():
    abstract = "We propose the Transformer, a model architecture eschewing recurrence."
    # Exact quote
    quote1 = "model architecture eschewing recurrence"
    assert enforce_verbatim_grounding(quote1, abstract) == quote1

    # Hallucinated quote
    quote2 = "Transformers are completely revolutionary and better than everything"
    assert enforce_verbatim_grounding(quote2, abstract) == ""
    print("✓ Enforce verbatim grounding test passed")


def test_db_crud():
    loop = asyncio.new_event_loop()
    async def run_db():
        doc_id = "test-doc-123"
        doc = await insert_document(doc_id, "test.pdf", "Some text")
        assert doc["id"] == doc_id
        assert doc["status"] == "uploaded"

        updated = await update_document_status(doc_id, "extracting_claims")
        assert updated["status"] == "extracting_claims"

        fetched = await get_document(doc_id)
        assert fetched["status"] == "extracting_claims"

        claims = [
            {
                "id": "c1",
                "document_id": doc_id,
                "claim_text": "Claim 1",
                "in_text_citation": "[1]",
                "reference_string": "Ref 1",
                "search_query": "Query 1",
                "verdict": "Supported",
                "confidence": 0.95,
                "explanation": "Verified",
                "evidence_passage": "Evidence",
            }
        ]
        await insert_claims(claims)
        fetched_claims = await get_claims_for_document(doc_id)
        assert len(fetched_claims) >= 1
        assert fetched_claims[0]["verdict"] == "Supported"

    loop.run_until_complete(run_db())
    loop.close()
    print("✓ Database CRUD test passed")


def test_upload_and_flow():
    pdf_bytes = create_sample_pdf()
    files = {"file": ("sample_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "document_id" in data
    doc_id = data["document_id"]
    assert data["filename"] == "sample_paper.pdf"
    assert data["status"] == "uploaded"

    # Check results before analysis
    res_results = client.get(f"/api/results/{doc_id}")
    assert res_results.status_code == 200
    res_data = res_results.json()
    assert res_data["document_id"] == doc_id
    assert res_data["status"] == "uploaded"
    assert res_data["summary"]["total_claims"] == 0

    # Check history
    res_hist = client.get("/api/history")
    assert res_hist.status_code == 200
    hist_list = res_hist.json()
    assert any(h["document_id"] == doc_id for h in hist_list)

    # Check report generation
    res_report = client.get(f"/api/report/{doc_id}")
    assert res_report.status_code == 200
    assert "CiteVerify Academic Verification Report" in res_report.text
    print("✓ Upload, Results, History, and Report endpoints passed")


def test_end_to_end_mocked_pipeline():
    # Test full analyze pipeline with mocked extraction, research, and verification
    pdf_bytes = create_sample_pdf()
    upload_res = client.post(
        "/api/upload",
        files={"file": ("test_analysis.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = upload_res.json()["document_id"]

    mock_claims = ExtractedClaimsResponse(
        claims=[
            ExtractedClaim(
                claim_text="Transformers outperform RNNs on translation tasks.",
                in_text_citation="[1]",
                reference_string="Vaswani et al., Attention is All You Need, 2017.",
                search_query="Attention is All You Need",
            )
        ]
    )

    mock_source = {
        "title": "Attention is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "year": 2017,
        "doi": "https://doi.org/10.48550/arXiv.1706.03762",
        "url": "https://arxiv.org/abs/1706.03762",
        "abstract": "The Transformer allows for significantly more parallelization and establishes a new state of the art in translation quality.",
    }

    mock_judgment = VerificationJudgment(
        verdict="Supported",
        confidence=0.98,
        explanation="The abstract explicitly establishes that Transformers establish a new state of the art in translation quality.",
        evidence_passage="establishes a new state of the art in translation quality",
    )

    with patch("app.main.extract_claims", new_callable=AsyncMock) as mock_extract, \
         patch("app.main.search_source", new_callable=AsyncMock) as mock_search, \
         patch("app.main.verify_claim", new_callable=AsyncMock) as mock_verify:

        mock_extract.return_value = mock_claims
        mock_search.return_value = mock_source
        mock_verify.return_value = mock_judgment

        # Call analyze
        analyze_res = client.post(f"/api/analyze/{doc_id}")
        assert analyze_res.status_code == 200
        assert analyze_res.json()["status"] == "extracting_claims"

        # Note: TestClient runs background tasks synchronously before returning!
        # Check results
        results_res = client.get(f"/api/results/{doc_id}")
        assert results_res.status_code == 200
        res_data = results_res.json()
        assert res_data["status"] == "completed"
        assert res_data["summary"]["total_claims"] == 1
        assert res_data["summary"]["supported"] == 1
        assert len(res_data["claims"]) == 1
        assert res_data["claims"][0]["verdict"] == "Supported"
        assert res_data["claims"][0]["confidence"] == 0.98

        # Download report
        rep_res = client.get(f"/api/report/{doc_id}")
        assert rep_res.status_code == 200
        assert "Attention is All You Need" in rep_res.text
        assert "Supported" in rep_res.text

    print("✓ End-to-end pipeline test passed")


if __name__ == "__main__":
    test_health()
    test_pdf_parser()
    test_research_api_helpers()
    test_verifier_no_abstract()
    test_enforce_verbatim_grounding()
    test_db_crud()
    test_upload_and_flow()
    test_end_to_end_mocked_pipeline()
    print("\nALL BACKEND UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")
