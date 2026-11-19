import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from functools import lru_cache
from supabase import create_client, Client

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback in-memory stores for resilience during tests or before tables are initialized
_MEMORY_DOCUMENTS: Dict[str, Dict[str, Any]] = {}
_MEMORY_CLAIMS: Dict[str, List[Dict[str, Any]]] = {}


def get_current_iso_time() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache()
def get_supabase_client() -> Optional[Client]:
    """Returns a cached Supabase client if valid credentials are provided."""
    url = settings.SUPABASE_URL.strip()
    key = settings.SUPABASE_KEY.strip()
    if url and key:
        try:
            return create_client(url, key)
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase client: {e}")
    return None


async def insert_document(
    doc_id: str,
    filename: str,
    extracted_text: str,
    status: str = "uploaded",
) -> Dict[str, Any]:
    """Inserts a new document record into Supabase (with in-memory fallback)."""
    now = get_current_iso_time()
    record = {
        "id": doc_id,
        "filename": filename,
        "extracted_text": extracted_text,
        "status": status,
        "error_message": None,
        "created_at": now,
    }

    # Store in memory
    _MEMORY_DOCUMENTS[doc_id] = record

    client = get_supabase_client()
    if client:
        try:
            res = client.table("documents").insert(record).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.warning(f"Supabase insert_document failed, using local store: {e}")

    return record


async def update_document_status(
    doc_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Updates status and optional error message for a document."""
    update_data = {
        "status": status,
        "error_message": error_message,
    }

    # Update memory
    if doc_id in _MEMORY_DOCUMENTS:
        _MEMORY_DOCUMENTS[doc_id].update(update_data)
        updated_doc = _MEMORY_DOCUMENTS[doc_id]
    else:
        updated_doc = {"id": doc_id, **update_data}

    client = get_supabase_client()
    if client:
        try:
            res = client.table("documents").update(update_data).eq("id", doc_id).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.warning(f"Supabase update_document_status failed, using local store: {e}")

    return updated_doc


async def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a document by its ID."""
    client = get_supabase_client()
    if client:
        try:
            res = client.table("documents").select("*").eq("id", doc_id).execute()
            if res.data and len(res.data) > 0:
                doc = res.data[0]
                _MEMORY_DOCUMENTS[doc_id] = doc
                return doc
        except Exception as e:
            logger.warning(f"Supabase get_document failed, checking local store: {e}")

    return _MEMORY_DOCUMENTS.get(doc_id)


async def get_recent_documents(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent documents ordered by created_at DESC."""
    client = get_supabase_client()
    if client:
        try:
            res = (
                client.table("documents")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            if res.data is not None:
                return res.data
        except Exception as e:
            logger.warning(f"Supabase get_recent_documents failed, returning local store: {e}")

    # Fallback to memory
    docs = list(_MEMORY_DOCUMENTS.values())
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return docs[:limit]


async def insert_claims(claims_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inserts a batch of verified claims for a document."""
    if not claims_data:
        return []

    # Store in memory
    for c in claims_data:
        doc_id = c.get("document_id")
        if doc_id:
            if doc_id not in _MEMORY_CLAIMS:
                _MEMORY_CLAIMS[doc_id] = []
            _MEMORY_CLAIMS[doc_id].append(c)

    client = get_supabase_client()
    if client:
        try:
            res = client.table("claims").insert(claims_data).execute()
            if res.data:
                return res.data
        except Exception as e:
            logger.warning(f"Supabase insert_claims failed, using local store: {e}")

    return claims_data


async def get_claims_for_document(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieves all claims associated with a given document_id."""
    client = get_supabase_client()
    if client:
        try:
            res = client.table("claims").select("*").eq("document_id", doc_id).execute()
            if res.data is not None and len(res.data) > 0:
                _MEMORY_CLAIMS[doc_id] = res.data
                return res.data
        except Exception as e:
            logger.warning(f"Supabase get_claims_for_document failed, using local store: {e}")

    return _MEMORY_CLAIMS.get(doc_id, [])
