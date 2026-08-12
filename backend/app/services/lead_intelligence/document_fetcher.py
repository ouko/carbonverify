"""Generic registry document download, scan, and storage."""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.config import get_settings
from app.models import LeadDocument, LeadDocumentStatusEnum
from app.services.clamav_scanner import get_scanner, ScanStatus

logger = get_logger(__name__)
settings = get_settings()


class RegistryDocumentFetcher:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            },
        )

    async def fetch_document(
        self,
        lead_document: LeadDocument,
        lead_id: str,
        registry_source: str,
    ) -> LeadDocument:
        """Download, scan, and store a single registry document.

        Args:
            lead_document: The document record to fetch.
            lead_id: UUID of the parent lead as a string.
            registry_source: Registry source slug (e.g. "cdm", "verra").

        Returns the updated LeadDocument. Does NOT commit the DB session.
        """
        lead_document.fetch_attempts = (lead_document.fetch_attempts or 0) + 1
        lead_document.last_fetch_attempt_at = datetime.now(timezone.utc)

        try:
            logger.info(
                "fetching_lead_document",
                lead_document_id=str(lead_document.id),
                attempt=lead_document.fetch_attempts,
            )
            headers = {}
            if lead_document.etag:
                headers["If-None-Match"] = lead_document.etag
            if lead_document.last_modified:
                headers["If-Modified-Since"] = lead_document.last_modified

            resp = await self.client.get(lead_document.source_url, headers=headers)

            if resp.status_code == 304:
                logger.info(
                    "lead_document_not_modified",
                    lead_document_id=str(lead_document.id),
                    source_url=lead_document.source_url,
                )
                lead_document.status = LeadDocumentStatusEnum.fetched
                lead_document.fetched_at = datetime.now(timezone.utc)
                lead_document.error_message = None
                return lead_document

            resp.raise_for_status()
            content = resp.content

            file_hash = hashlib.sha256(content).hexdigest()
            mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
            file_size = len(content)

            # Virus scan. Infected files are rejected; scan errors are logged but
            # do not block the fetch because ClamAV may be unavailable.
            scan_result = await get_scanner().scan_buffer(content)
            if scan_result.status == ScanStatus.infected:
                logger.warning(
                    "lead_document_infected",
                    lead_document_id=str(lead_document.id),
                    signature=scan_result.signature,
                )
                lead_document.status = LeadDocumentStatusEnum.failed
                lead_document.error_message = (
                    f"Virus detected: {scan_result.signature}"
                    if scan_result.signature
                    else "Virus detected"
                )
                return lead_document
            elif scan_result.status == ScanStatus.error:
                logger.warning(
                    "lead_document_scan_error",
                    lead_document_id=str(lead_document.id),
                    message=scan_result.message,
                )

            s3_key = self._build_s3_key(
                lead_id=lead_id,
                registry_source=registry_source,
                document_type=lead_document.document_type,
                mime_type=mime_type,
                file_hash=file_hash,
            )
            s3_bucket = settings.S3_BUCKET_NAME
            await self._upload_to_s3(s3_key, content, mime_type)

            lead_document.status = LeadDocumentStatusEnum.fetched
            lead_document.file_hash_sha256 = file_hash
            lead_document.s3_key = s3_key
            lead_document.s3_bucket = s3_bucket
            lead_document.file_size_bytes = file_size
            lead_document.mime_type = mime_type
            lead_document.fetched_at = datetime.now(timezone.utc)
            lead_document.error_message = None
            lead_document.etag = resp.headers.get("etag") or lead_document.etag
            lead_document.last_modified = resp.headers.get("last-modified") or lead_document.last_modified

            logger.info(
                "lead_document_fetched",
                lead_document_id=str(lead_document.id),
                file_hash=file_hash,
                s3_key=s3_key,
            )
        except Exception as exc:
            logger.error(
                "lead_document_fetch_failed",
                lead_document_id=str(lead_document.id),
                error=str(exc),
            )
            lead_document.status = LeadDocumentStatusEnum.failed
            lead_document.error_message = str(exc)[:1000]

        return lead_document

    def _build_s3_key(
        self,
        lead_id: str,
        registry_source: str,
        document_type: str,
        mime_type: str,
        file_hash: str,
    ) -> str:
        ext = self._guess_extension(mime_type or "")
        source = registry_source or "unknown"
        return f"leads/{source}/{lead_id}/{document_type}/{file_hash}{ext}"

    @staticmethod
    def _guess_extension(mime_type: str) -> str:
        mapping = {
            "application/pdf": ".pdf",
            "text/html": ".html",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        }
        return mapping.get(mime_type, "")

    async def _upload_to_s3(self, s3_key: str, content: bytes, mime_type: str) -> None:
        import boto3

        def _put():
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION or "us-east-1",
            )
            s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=content,
                ContentType=mime_type,
            )

        await asyncio.to_thread(_put)

    async def close(self) -> None:
        await self.client.aclose()
