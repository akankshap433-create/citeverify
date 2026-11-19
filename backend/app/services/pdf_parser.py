import re
import pymupdf as fitz  # PyMuPDF


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts clean text from raw PDF bytes using PyMuPDF (fitz).
    Preserves document structure while cleaning up control characters and excessive whitespace.
    """
    if not pdf_bytes:
        raise ValueError("PDF content is empty.")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Failed to read PDF file: {str(e)}")

    extracted_pages = []
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")
            if text and text.strip():
                extracted_pages.append(text.strip())
    finally:
        doc.close()

    if not extracted_pages:
        return ""

    combined_text = "\n\n".join(extracted_pages)
    
    # Clean up non-printable control characters (except tabs and newlines)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", combined_text)
    # Normalize line breaks
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize multiple newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    return cleaned.strip()
