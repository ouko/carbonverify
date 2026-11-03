"""IngestionAgent: assesses project data ingestion status and data quality."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.agents.base import BLEND_FORMULA, AgentResult, BaseAgent
from app.models import DataSource, FileUpload
from app.core.logging import get_logger

logger = get_logger(__name__)

# A file upload stuck in these statuses longer than this is a stale source.
STALE_UPLOAD_DAYS = 7
# Implausible bounds for numeric values found in processing results.
OUT_OF_RANGE_ABS_LIMIT = 1e9

ANOMALY_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "anomaly_severity": {"type": "number", "description": "0 = no concern, 1 = severe data quality risk"},
        "summary": {"type": "string"},
        "recommended_action": {"type": "string"},
    },
    "required": ["anomaly_severity", "summary"],
}


class IngestionAgent(BaseAgent):
    """Agent responsible for ingesting and processing uploaded data files.

    Performs real (DB-backed) ingestion assessment: per-upload pipeline
    validation, data-completeness scoring, and anomaly detection
    (duplicate hashes, out-of-range values, stale sources). Pending async
    pipeline work is reported as queued rather than simulated.
    """

    agent_type = "ingestion"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Assess ingestion state for the project."""
        project_id = self.project_id

        upload_result = await self.db.execute(
            select(FileUpload).where(FileUpload.project_id == project_id)
        )
        uploads = upload_result.scalars().all()

        ds_result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        data_sources = ds_result.scalars().all()

        if not uploads and not data_sources:
            reasoning = (
                "No file uploads or data sources exist for this project yet. "
                "Nothing to ingest; confidence set to 0.6 pending first data delivery."
            )
            return AgentResult(
                status="completed",
                confidence_score=0.6,
                output_data=self.build_output(
                    reasoning,
                    {"uploads": 0, "data_sources": 0},
                    processed_count=0,
                    queued_count=0,
                    failed_count=0,
                ),
                reasoning=reasoning,
                evidence={"uploads": 0, "data_sources": 0},
            )

        now = datetime.now(timezone.utc)
        processed_count = 0
        queued_count = 0
        failed_count = 0
        anomalies: List[Dict[str, Any]] = []

        # 1. Per-upload pipeline-appropriate validation on DB state.
        for upload in uploads:
            status = upload.status.value if hasattr(upload.status, "value") else str(upload.status)
            if status == "completed":
                processed_count += 1
            elif status in ("uploaded", "processing"):
                queued_count += 1
            elif status == "failed":
                failed_count += 1

            upload_anomalies = self._validate_upload(upload, now)
            anomalies.extend(upload_anomalies)

        # 2. Duplicate detection across uploads (identical SHA-256 content).
        anomalies.extend(self._detect_duplicate_uploads(uploads))

        # 3. Data-source validation status and out-of-range processed values.
        valid_sources = 0
        flagged_sources = 0
        for ds in data_sources:
            validation_status = (
                ds.validation_status.value if hasattr(ds.validation_status, "value") else str(ds.validation_status)
            )
            if validation_status == "valid":
                valid_sources += 1
            elif validation_status in ("flagged", "rejected"):
                flagged_sources += 1
                anomalies.append({
                    "type": "source_flagged",
                    "source_id": str(ds.id),
                    "detail": f"Data source has validation_status '{validation_status}'",
                })
            anomalies.extend(self._detect_out_of_range(ds))

        # 4. Stale sources: uploads stuck pre-completion or sources never validated.
        for upload in uploads:
            status = upload.status.value if hasattr(upload.status, "value") else str(upload.status)
            created_at = upload.created_at
            if status in ("uploaded", "processing") and created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_days = (now - created_at).days
                if age_days >= STALE_UPLOAD_DAYS:
                    anomalies.append({
                        "type": "stale_source",
                        "upload_id": str(upload.id),
                        "detail": (
                            f"Upload '{upload.original_filename}' stuck in '{status}' "
                            f"for {age_days} days (threshold {STALE_UPLOAD_DAYS})"
                        ),
                    })
        for ds in data_sources:
            validation_status = (
                ds.validation_status.value if hasattr(ds.validation_status, "value") else str(ds.validation_status)
            )
            created_at = ds.created_at
            if validation_status == "pending" and created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_days = (now - created_at).days
                if age_days >= STALE_UPLOAD_DAYS:
                    anomalies.append({
                        "type": "stale_source",
                        "source_id": str(ds.id),
                        "detail": f"Data source unvalidated for {age_days} days (threshold {STALE_UPLOAD_DAYS})",
                    })

        # 5. Completeness: received vs expected processing outcomes.
        total_uploads = len(uploads)
        completed_or_failed = processed_count + failed_count
        if total_uploads > 0:
            completeness = completed_or_failed / total_uploads
        elif data_sources:
            completeness = 1.0
        else:
            completeness = 0.0

        # Heuristic confidence: completeness penalized by anomaly density.
        anomaly_penalty = min(0.4, 0.1 * len(anomalies))
        heuristic = max(0.0, completeness - anomaly_penalty)

        # 6. LLM review of the anomaly list (falls back to heuristic-only).
        top_anomalies = anomalies[:5]
        llm_review = await self.reason_with_llm(
            task_prompt=(
                "Review this project's ingestion anomaly list. Rate overall anomaly "
                "severity from 0 (no concern) to 1 (severe data quality risk) and "
                "recommend an action."
            ),
            context={
                "project_id": str(project_id),
                "uploads": total_uploads,
                "data_sources": len(data_sources),
                "processed": processed_count,
                "queued": queued_count,
                "failed": failed_count,
                "anomalies": top_anomalies,
            },
            response_schema=ANOMALY_REVIEW_SCHEMA,
        )
        llm_score = self._extract_llm_score(llm_review)
        if llm_score is not None:
            confidence = self.blend_confidence(heuristic, 1.0 - llm_score)
            blend_note = f"Confidence blended via LLM anomaly review ({BLEND_FORMULA})."
        else:
            confidence = self.blend_confidence(heuristic)
            blend_note = (
                "LLM review unavailable; confidence is the heuristic completeness "
                f"score alone (blending {BLEND_FORMULA} not applied)."
            )

        anomaly_summary = "; ".join(a["detail"] for a in top_anomalies) if top_anomalies else "none"
        reasoning = (
            f"Assessed {total_uploads} upload(s) and {len(data_sources)} data source(s): "
            f"{processed_count} processed, {queued_count} queued for async pipeline, "
            f"{failed_count} failed, {valid_sources} sources valid, {flagged_sources} flagged. "
            f"Completeness {completeness:.2f} with {len(anomalies)} anomaly(ies) — top: {anomaly_summary}. "
            f"{blend_note}"
        )

        evidence = {
            "upload_count": total_uploads,
            "data_source_count": len(data_sources),
            "processed_count": processed_count,
            "queued_count": queued_count,
            "failed_count": failed_count,
            "valid_source_count": valid_sources,
            "flagged_source_count": flagged_sources,
            "completeness": round(completeness, 3),
            "anomaly_count": len(anomalies),
            "anomalies": top_anomalies,
            "llm_review": None if llm_review.get("_fallback") else llm_review,
        }

        output = self.build_output(
            reasoning,
            evidence,
            processed_count=processed_count,
            queued_count=queued_count,
            failed_count=failed_count,
            completeness=round(completeness, 3),
            anomaly_count=len(anomalies),
            anomalies=top_anomalies,
        )

        if failed_count > 0 or confidence < 0.85:
            status = "queued_for_review"
        else:
            status = "completed"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            errors=[a["detail"] for a in anomalies if a["type"] in ("upload_invalid", "source_flagged")][:5] or None,
            reasoning=reasoning,
            evidence=evidence,
        )

    # ─── Validation helpers ───────────────────────────────────────────────

    def _validate_upload(self, upload: FileUpload, now: datetime) -> List[Dict[str, Any]]:
        """Pipeline-appropriate structural validation of a single upload record."""
        anomalies: List[Dict[str, Any]] = []
        detected = (
            upload.detected_type.value if hasattr(upload.detected_type, "value") else str(upload.detected_type)
        )

        if detected == "unknown":
            anomalies.append({
                "type": "upload_invalid",
                "upload_id": str(upload.id),
                "detail": f"Upload '{upload.original_filename}' has unknown detected type",
            })
        if not upload.file_hash_sha256 or len(upload.file_hash_sha256) != 64:
            anomalies.append({
                "type": "upload_invalid",
                "upload_id": str(upload.id),
                "detail": f"Upload '{upload.original_filename}' missing valid SHA-256 hash",
            })
        if upload.file_size_bytes is not None and upload.file_size_bytes <= 0:
            anomalies.append({
                "type": "out_of_range_value",
                "upload_id": str(upload.id),
                "detail": f"Upload '{upload.original_filename}' has non-positive size {upload.file_size_bytes}",
            })
        return anomalies

    def _detect_duplicate_uploads(self, uploads: List[FileUpload]) -> List[Dict[str, Any]]:
        """Flag uploads sharing an identical SHA-256 hash (re-submissions)."""
        seen: Dict[str, str] = {}
        anomalies: List[Dict[str, Any]] = []
        for upload in uploads:
            file_hash = upload.file_hash_sha256
            if not file_hash:
                continue
            if file_hash in seen:
                anomalies.append({
                    "type": "duplicate_upload",
                    "upload_id": str(upload.id),
                    "detail": (
                        f"Upload '{upload.original_filename}' duplicates content of "
                        f"'{seen[file_hash]}' (sha256 {file_hash[:12]}...)"
                    ),
                })
            else:
                seen[file_hash] = upload.original_filename
        return anomalies

    def _detect_out_of_range(self, ds: DataSource) -> List[Dict[str, Any]]:
        """Flag implausible numeric values in a source's processed data."""
        anomalies: List[Dict[str, Any]] = []
        processed = ds.processed_data or {}
        for key, value in processed.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if abs(value) > OUT_OF_RANGE_ABS_LIMIT or value < 0:
                    anomalies.append({
                        "type": "out_of_range_value",
                        "source_id": str(ds.id),
                        "detail": f"Field '{key}' = {value} is out of plausible range",
                    })
        return anomalies

    @staticmethod
    def _extract_llm_score(llm_review: Dict[str, Any]) -> "Optional[float]":
        """Pull a numeric anomaly_severity out of an LLM review, or None if unusable."""
        if llm_review.get("_fallback"):
            return None
        severity = llm_review.get("anomaly_severity")
        if isinstance(severity, (int, float)) and not isinstance(severity, bool):
            return max(0.0, min(1.0, float(severity)))
        return None
