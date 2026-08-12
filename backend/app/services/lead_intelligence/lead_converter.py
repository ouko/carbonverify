"""Convert a qualified Lead and its fetched documents into a CarbonVerify Project."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models import (
    DataSource,
    DetectedFileTypeEnum,
    FileUpload,
    FileUploadStatusEnum,
    Lead,
    LeadDocument,
    LeadDocumentStatusEnum,
    LeadWorkflowStatusEnum,
    MethodologyEnum,
    Project,
    ProjectStatusEnum,
    SourceTypeEnum,
    ValidationStatusEnum,
)
from app.services.lead_intelligence.system_developer import get_or_create_system_developer

logger = get_logger(__name__)


class LeadConversionError(Exception):
    pass


class LeadToProjectConverter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def convert(self, lead: Lead) -> Project:
        """Convert a lead into a project with file uploads and data sources."""
        self._validate_lead(lead)

        developer = await get_or_create_system_developer(self.db)

        methodology = self._map_methodology(lead.methodology)

        project = Project(
            name=lead.project_name,
            developer_id=developer.id,
            methodology=methodology,
            crediting_period_start=lead.crediting_period_start,
            crediting_period_end=lead.crediting_period_end,
            status=ProjectStatusEnum.onboarding,
        )
        self.db.add(project)
        await self.db.flush()

        docs_result = await self.db.execute(
            select(LeadDocument).where(
                LeadDocument.lead_id == lead.id,
                LeadDocument.status == LeadDocumentStatusEnum.fetched,
            )
        )
        fetched_docs = docs_result.scalars().all()

        registry_source = lead.registry_source.value if lead.registry_source else "unknown"
        for doc in fetched_docs:
            await self._attach_document(project.id, doc, registry_source)

        lead.converted_project_id = project.id
        lead.lead_status = LeadWorkflowStatusEnum.converted
        lead.updated_at = datetime.now(timezone.utc)

        await self.db.commit()

        # Eager-load relationships so callers can access file_uploads/data_sources
        # without triggering async lazy loads.
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project.id)
            .options(selectinload(Project.file_uploads), selectinload(Project.data_sources))
        )
        project = result.scalar_one()

        logger.info("lead_converted_to_project", lead_id=str(lead.id), project_id=str(project.id))
        return project

    def _validate_lead(self, lead: Lead) -> None:
        if lead.converted_project_id is not None:
            raise LeadConversionError("Lead has already been converted")
        if not lead.crediting_period_start or not lead.crediting_period_end:
            raise LeadConversionError("Lead is missing crediting period dates")
        if lead.crediting_period_end <= lead.crediting_period_start:
            raise LeadConversionError("Crediting period end must be after start")

    def _map_methodology(self, value: Optional[str]) -> MethodologyEnum:
        if not value:
            return MethodologyEnum.TPDDTEC_v4
        mapping = {
            "TPDDTEC_v4": MethodologyEnum.TPDDTEC_v4,
            "VM0050": MethodologyEnum.VM0050,
            "VMR0006": MethodologyEnum.VMR0006,
            "AMS-II.G": MethodologyEnum.AMS_II_G,
        }
        for key, enum in mapping.items():
            if key.lower() == value.lower():
                return enum
        return MethodologyEnum.TPDDTEC_v4

    async def _attach_document(self, project_id, doc: LeadDocument, registry_source: str) -> None:
        detected_type = self._detected_type(doc.mime_type)
        upload = FileUpload(
            project_id=project_id,
            original_filename=doc.title or f"{doc.document_type}.{detected_type}",
            detected_type=detected_type,
            mime_type=doc.mime_type or "application/octet-stream",
            s3_key=doc.s3_key or "",
            s3_bucket=doc.s3_bucket or "",
            file_size_bytes=doc.file_size_bytes or 0,
            file_hash_sha256=doc.file_hash_sha256 or "",
            status=FileUploadStatusEnum.uploaded,
            provenance={
                "source": "registry_import",
                "lead_document_id": str(doc.id),
                "registry_source": registry_source,
            },
        )
        self.db.add(upload)
        await self.db.flush()

        doc.file_upload_id = upload.id

        data_source = DataSource(
            project_id=project_id,
            source_type=SourceTypeEnum.document,
            schema_version="1.0",
            raw_data={
                "document_type": doc.document_type,
                "source_url": doc.source_url,
                "mime_type": doc.mime_type,
                "file_upload_id": str(upload.id),
            },
            validation_status=ValidationStatusEnum.pending,
            provenance={"lead_document_id": str(doc.id)},
        )
        self.db.add(data_source)

    def _detected_type(self, mime_type: Optional[str]) -> DetectedFileTypeEnum:
        if mime_type == "application/pdf":
            return DetectedFileTypeEnum.pdf
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ):
            return DetectedFileTypeEnum.excel
        if mime_type == "text/csv":
            return DetectedFileTypeEnum.csv
        return DetectedFileTypeEnum.unknown
