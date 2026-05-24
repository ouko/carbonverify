import hashlib
from datetime import datetime
from typing import Tuple, Optional
import magic
from app.core.logging import get_logger
from app.models import DetectedFileTypeEnum

logger = get_logger(__name__)

# Magic bytes signatures for common file types
MAGIC_SIGNATURES = {
    b'\x50\x4b\x03\x04': ('excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),  # xlsx
    b'\xd0\xcf\x11\xe0': ('excel', 'application/vnd.ms-excel'),  # xls
    b'%PDF': ('pdf', 'application/pdf'),
    b'\xff\xd8\xff': ('image', 'image/jpeg'),  # jpg/jpeg
    b'\x89PNG': ('image', 'image/png'),
    b'RIFF': ('image', 'image/webp'),  # webp starts with RIFF....WEBP
}


def detect_file_type(file_bytes: bytes) -> Tuple[DetectedFileTypeEnum, str]:
    """Detect file type by magic bytes, falling back to extension-based hints."""
    # Try magic bytes first
    for sig, (ftype, mime) in MAGIC_SIGNATURES.items():
        if file_bytes.startswith(sig):
            # Special handling for webp inside RIFF
            if sig == b'RIFF' and len(file_bytes) >= 12:
                if file_bytes[8:12] == b'WEBP':
                    return DetectedFileTypeEnum.image, 'image/webp'
                continue
            return DetectedFileTypeEnum(ftype), mime

    # Try python-magic for broader detection
    try:
        mime = magic.from_buffer(file_bytes, mime=True)
        if mime in [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
        ]:
            return DetectedFileTypeEnum.excel, mime
        elif mime == 'text/csv':
            return DetectedFileTypeEnum.csv, mime
        elif mime == 'application/pdf':
            return DetectedFileTypeEnum.pdf, mime
        elif mime.startswith('image/'):
            return DetectedFileTypeEnum.image, mime
    except Exception as e:
        logger.warning("magic_detection_failed", error=str(e))

    # CSV fallback: check if content looks like CSV
    try:
        sample = file_bytes[:4096].decode('utf-8', errors='ignore')
        lines = sample.strip().split('\n')
        if len(lines) >= 2 and ',' in lines[0]:
            return DetectedFileTypeEnum.csv, 'text/csv'
    except Exception:
        pass

    return DetectedFileTypeEnum.unknown, 'application/octet-stream'


def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def generate_s3_key(project_id: str, source_type: str, filename: str) -> str:
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
    safe_filename = filename.replace(' ', '_')
    return f"{project_id}/{source_type}/{timestamp}/{safe_filename}"
