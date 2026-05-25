import io
import re
from typing import Dict, Any, List

import pdfplumber
from PyPDF2 import PdfReader

from app.core.logging import get_logger
from app.models import DocumentTypeEnum

logger = get_logger(__name__)

DOCUMENT_PATTERNS = {
    DocumentTypeEnum.monitoring_report: [
        r"monitoring\s*report",
        r"emissions\s*reduction",
        r"monitoring\s*period",
    ],
    DocumentTypeEnum.kpt_results: [
        r"kitchen\s*performance\s*test",
        r"kpt",
        r"fuel\s*consumption\s*test",
    ],
    DocumentTypeEnum.sales_receipt: [
        r"receipt",
        r"invoice",
        r"sales\s*order",
        r"purchase\s*order",
    ],
    DocumentTypeEnum.survey_form: [
        r"survey",
        r"questionnaire",
        r"baseline\s*survey",
        r"follow.up\s*survey",
    ],
}

KEY_VALUE_PATTERNS = [
    r"(?P<key>[A-Z][A-Za-z\s]+):\s*(?P<value>[^\n]+)",
    r"(?P<key>[A-Z][A-Za-z_]+)\s*=\s*(?P<value>[^\n]+)",
    r"(?P<key>[A-Za-z_]+)\s*:\s*(?P<value>[^\n]+)",
]


def extract_text_pdfplumber(file_bytes: bytes) -> str:
    """Extract text using pdfplumber (better for tables and layouts)."""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.warning("pdfplumber_extraction_failed", error=str(e))
    return text


def extract_text_pypdf2(file_bytes: bytes) -> str:
    """Extract text using PyPDF2 as fallback."""
    text = ""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        logger.warning("pypdf2_extraction_failed", error=str(e))
    return text


def classify_document(text: str) -> DocumentTypeEnum:
    """Classify document type based on keyword patterns."""
    text_lower = text.lower()
    scores = {}
    for doc_type, patterns in DOCUMENT_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, text_lower))
        scores[doc_type] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return DocumentTypeEnum.other
    return best


def extract_key_value_pairs(text: str) -> Dict[str, str]:
    """Extract key-value pairs from document text."""
    pairs = {}
    for pattern in KEY_VALUE_PATTERNS:
        matches = re.finditer(pattern, text)
        for m in matches:
            key = m.group("key").strip().lower().replace(" ", "_")
            value = m.group("value").strip()
            if key and value and len(key) < 100 and len(value) < 500:
                pairs[key] = value
    return pairs


def extract_dates(text: str) -> List[str]:
    """Extract date strings from text."""
    date_patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b\d{2}-\d{2}-\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",
    ]
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, text))
    return dates


def process_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Process PDF file and return structured result."""
    logger.info("processing_pdf", filename=filename)

    result = {
        "filename": filename,
        "detected_type": "pdf",
        "text_length": 0,
        "num_pages": 0,
        "document_type": DocumentTypeEnum.other.value,
        "key_value_pairs": {},
        "dates_found": [],
        "tables_found": 0,
        "is_scanned": False,
        "validation_errors": [],
        "ocr_text": None,
    }

    # Try PyPDF2 for page count
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        result["num_pages"] = len(reader.pages)
    except Exception as e:
        result["validation_errors"].append(f"Could not read PDF structure: {str(e)}")
        return result

    # Extract text
    text = extract_text_pdfplumber(file_bytes)
    if not text.strip():
        text = extract_text_pypdf2(file_bytes)

    result["text_length"] = len(text)

    # Detect if scanned (very little extractable text)
    if result["text_length"] < 100 and result["num_pages"] > 0:
        result["is_scanned"] = True
        result["validation_errors"].append(
            "PDF appears to be scanned/image-based. OCR may be required for full text extraction."
        )
        # Note: Actual OCR with pytesseract would require poppler/tesseract installed
        # and image extraction from PDF pages. We flag it here.

    # Classify document
    if text:
        doc_type = classify_document(text)
        result["document_type"] = doc_type.value

    # Extract key-value pairs
    if text:
        result["key_value_pairs"] = extract_key_value_pairs(text)
        result["dates_found"] = extract_dates(text)

    # Count tables with pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.find_tables()
                if tables:
                    result["tables_found"] += len(tables)
    except Exception:
        logger.debug("pdf_table_extraction_failed", exc_info=True)

    logger.info(
        "pdf_processed",
        filename=filename,
        pages=result["num_pages"],
        doc_type=result["document_type"],
        is_scanned=result["is_scanned"],
    )
    return result
