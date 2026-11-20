from typing import Literal, Optional, List
from pydantic import BaseModel, Field

# VerdictLiteral specification
VerdictLiteral = Literal[
    "Supported",
    "Partially Supported",
    "Unsupported",
    "Contradictory",
    "Potentially Outdated",
    "Unable to Verify",
]


class ExtractedClaim(BaseModel):
    claim_text: str = Field(description="The scientific claim text extracted from the document.")
    in_text_citation: str = Field(description="The in-text citation marker, e.g. [1] or (Smith et al., 2020).")
    reference_string: str = Field(description="The full reference entry from the bibliography.")
    search_query: str = Field(description="Clean paper title of the cited work for research API lookup.")


class ExtractedClaimsResponse(BaseModel):
    claims: List[ExtractedClaim] = Field(default_factory=list, description="List of extracted claims from the paper.")


class VerificationJudgment(BaseModel):
    verdict: VerdictLiteral = Field(description="Evaluation verdict on whether the claim is supported.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")
    explanation: str = Field(description="Clear explanation justifying the verdict.")
    evidence_passage: str = Field(description="Verbatim quote directly from the retrieved abstract, or empty string.")


class SourceMetadata(BaseModel):
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None


class ClaimResult(BaseModel):
    id: Optional[str] = None
    document_id: str
    claim_text: str
    in_text_citation: str
    reference_string: str
    search_query: str
    verdict: VerdictLiteral
    confidence: float
    explanation: str
    evidence_passage: str
    source_title: Optional[str] = None
    source_authors: Optional[List[str]] = None
    source_year: Optional[int] = None
    source_doi: Optional[str] = None
    source_url: Optional[str] = None
    source_abstract: Optional[str] = None
    created_at: Optional[str] = None


class ClaimSummary(BaseModel):
    total_claims: int = 0
    supported: int = 0
    partially_supported: int = 0
    unsupported: int = 0
    contradictory: int = 0
    potentially_outdated: int = 0
    unable_to_verify: int = 0


class DocumentResultsResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    summary: ClaimSummary
    claims: List[ClaimResult] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str = "uploaded"


class DocumentAnalyzeResponse(BaseModel):
    document_id: str
    status: str
    message: str


class DocumentHistoryItem(BaseModel):
    document_id: str
    filename: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    total_claims: int = 0


class SuggestCitationsRequest(BaseModel):
    claim_text: str = Field(..., min_length=10, max_length=2000)


class SuggestedCitation(BaseModel):
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    why: str
    apa: str


class SuggestCitationsResponse(BaseModel):
    query: str
    suggestions: List[SuggestedCitation]
