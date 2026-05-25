"""IngestionAgent: processes uploaded data through appropriate pipelines."""

from typing import Any, Dict, List

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.models import DataSource, FileUpload, ValidationStatusEnum
from app.core.logging import get_logger

logger = get_logger(__name__)


class IngestionAgent(BaseAgent):
    """Agent responsible for ingesting and processing uploaded data files."""

    agent_type = "ingestion"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Process pending file uploads for the project."""
        project_id = self.project_id

        # Fetch pending uploads
        result = await self.db.execute(
            select(FileUpload).where(
                FileUpload.project_id == project_id,
                FileUpload.status.in_(["uploaded", "processing"]),
            )
        )
        uploads = result.scalars().all()

        if not uploads:
            return AgentResult(
                status="completed",
                confidence_score=1.0,
                output_data={"message": "No pending uploads", "processed_count": 0},
            )

        processed_count = 0
        failed_count = 0
        total_confidence = 0.0
        errors: List[str] = []

        for upload in uploads:
            try:
                # Simulate pipeline processing (actual pipelines would be called here)
                processing_result = self._simulate_pipeline(upload)
                upload.status = "completed"
                upload.processing_result = processing_result
                upload.confidence_score = processing_result.get("confidence", 0.9)
                total_confidence += upload.confidence_score
                processed_count += 1

                # Create or update DataSource record
                ds = DataSource(
                    project_id=project_id,
                    source_type=self._map_file_type_to_source(upload.detected_type.value),
                    schema_version="v1",
                    raw_data={"upload_id": str(upload.id), "filename": upload.original_filename},
                    processed_data=processing_result,
                    validation_status=ValidationStatusEnum.valid
                    if upload.confidence_score >= 0.85
                    else ValidationStatusEnum.flagged,
                    confidence_score=upload.confidence_score,
                )
                self.db.add(ds)

            except Exception as exc:
                upload.status = "failed"
                upload.validation_errors = [str(exc)]
                failed_count += 1
                errors.append(f"Upload {upload.id}: {exc}")
                logger.error("ingestion_failed", upload_id=str(upload.id), error=str(exc))

        await self.db.commit()

        # Calculate overall confidence
        avg_confidence = (
            total_confidence / processed_count if processed_count > 0 else 0.0
        )
        data_completeness = self._assess_data_completeness(processed_count, failed_count)

        # Confidence = weighted average of validation pass rate and data completeness
        confidence = (avg_confidence * 0.6) + (data_completeness * 0.4)

        output = {
            "processed_count": processed_count,
            "failed_count": failed_count,
            "avg_confidence": round(avg_confidence, 3),
            "data_completeness": round(data_completeness, 3),
            "upload_ids": [str(u.id) for u in uploads],
        }

        status = "completed" if failed_count == 0 else "queued_for_review"
        if confidence < 0.85:
            status = "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            errors=errors if errors else None,
        )

    def _simulate_pipeline(self, upload: FileUpload) -> Dict[str, Any]:
        """Simulate pipeline processing (integration point for real pipelines)."""
        return {
            "detected_type": upload.detected_type.value,
            "records_extracted": 150,
            "fields_mapped": 12,
            "confidence": 0.92,
            "validation_passed": True,
        }

    def _map_file_type_to_source(self, detected_type: str) -> str:
        mapping = {
            "excel": "mobile_survey",
            "csv": "mobile_survey",
            "pdf": "document",
            "image": "satellite",
        }
        return mapping.get(detected_type, "manual_entry")

    def _assess_data_completeness(self, processed: int, failed: int) -> float:
        total = processed + failed
        if total == 0:
            return 1.0
        return processed / total
