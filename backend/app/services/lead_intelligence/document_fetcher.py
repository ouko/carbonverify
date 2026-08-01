"""Generic registry document download, scan, and storage."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.config import get_settings
from app.models import LeadDocument, LeadDocumentStatusEnum

logger = get_logger(__name__)
settings = get_settings()


class RegistryDocumentFetcher:
    def __init__(self):
        self.client = httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            },
        )

    async def fetch_document(self, lead_document: LeadDocument) -> LeadDocument:
        """Download, scan, and store a single registry document.

        Returns the updated LeadDocument. Does NOT commit the DB session.
        """
        try:
            logger.info("fetching_lead_document", lead_document_id=str(lead_document.id))
            resp = self.client.get(lead_document.source_url)
            resp.raise_for_status()
            content = resp.content

            file_hash = hashlib.sha256(content).hexdigest()
            mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
            file_size = len(content)

            # Virus scan placeholder — integrate with existing ClamAV scanner if available
            # await scan_bytes(content)

            s3_key = self._build_s3_key(lead_document, file_hash)
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

            logger.info(
                "lead_document_fetched",
                lead_document_id=str(lead_document.id),
                file_hash=file_hash,
                s3_key=s3_key,
            )
        except Exception as exc:
            logger.error("lead_document_fetch_failed", lead_document_id=str(lead_document.id), error=str(exc))
            lead_document.status = LeadDocumentStatusEnum.failed
            lead_document.error_message = str(exc)[:1000]

        return lead_document

    def _build_s3_key(self, lead_document: LeadDocument, file_hash: str) -> str:
        lead = lead_document.lead
        ext = self._guess_extension(lead_document.mime_type or "")
        source = lead.registry_source.value if lead else "unknown"
        return f"leads/{source}/{lead.id}/{lead_document.document_type}/{file_hash}{ext}"

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

    def close(self) -> None:
        self.client.close()
