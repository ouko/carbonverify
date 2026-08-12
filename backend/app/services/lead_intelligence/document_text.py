"""Async helpers to fetch registry documents from S3 and extract text."""

import asyncio
from typing import Optional

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.services.pipelines.pdf import extract_text_pdfplumber, extract_text_pypdf

logger = get_logger(__name__)
settings = get_settings()


async def fetch_s3_bytes(s3_key: str, s3_bucket: Optional[str] = None) -> bytes:
    """Download object bytes from S3 in a thread pool."""
    bucket = s3_bucket or settings.S3_BUCKET_NAME

    def _get():
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION or "us-east-1",
        )
        return s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read()

    return await asyncio.to_thread(_get)


async def fetch_url_bytes(url: str) -> bytes:
    """Download object bytes from a public URL."""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def extract_text_from_bytes(content: bytes, mime_type: str) -> str:
    """Extract plain text from PDF or HTML bytes."""
    if mime_type == "application/pdf":
        text = extract_text_pdfplumber(content)
        if not text.strip():
            text = extract_text_pypdf(content)
        return text
    if mime_type == "text/html":
        from bs4 import BeautifulSoup
        return BeautifulSoup(content, "html.parser").get_text(separator="\n")
    return ""


async def extract_text_async(content: bytes, mime_type: str) -> str:
    """Thread-pool wrapper for text extraction."""
    return await asyncio.to_thread(extract_text_from_bytes, content, mime_type)
