"""Run the pre-audit validation workflow for a project and cache the result."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import DataSource, FileUpload, PreAuditStatusEnum, Project, ProjectPreAudit, SourceTypeEnum
from app.services.lead_intelligence.document_text import extract_text_async, fetch_s3_bytes
from app.services.lead_intelligence.pre_audit_workflow import get_or_create_pre_audit_workflow
from app.validation_engine.orchestrator import ValidationOrchestrator

logger = get_logger(__name__)

MAX_TEXT_CHARS_PER_DOC = 8000


class PreAuditRunner:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_for_project(self, project: Project, lead_id: str | None = None) -> ProjectPreAudit:
        """Create a validation run, execute it, and store the cached pre-audit result."""
        workflow = await get_or_create_pre_audit_workflow(self.db)
        excerpts = await self._build_document_excerpts(project.id)

        input_data = {
            "project_id": str(project.id),
            "project_name": project.name,
            "methodology": project.methodology.value,
            "document_excerpts": excerpts,
        }

        orchestrator = ValidationOrchestrator(self.db)
        run = await orchestrator.create_run(
            workflow_id=str(workflow.id),
            trigger_event="pre_audit_pipeline",
            input_data=input_data,
            project_id=str(project.id),
        )
        await orchestrator.execute_workflow(str(run.id))

        result = self._parse_run_output(run.output_data)
        readiness_score = result["score"]
        status = self._status_from_score(readiness_score, result.get("passed", False), result.get("risk_flags", []))

        pre_audit = ProjectPreAudit(
            project_id=project.id,
            lead_id=lead_id,
            validation_run_id=run.id,
            readiness_score=readiness_score,
            status=status,
            gap_summary={
                "gaps": result.get("gaps", []),
                "risk_flags": result.get("risk_flags", []),
                "recommendation": result.get("recommendation", ""),
                "reasoning": result.get("reasoning", ""),
            },
        )
        self.db.add(pre_audit)
        await self.db.commit()
        await self.db.refresh(pre_audit)
        logger.info(
            "pre_audit_completed",
            project_id=str(project.id),
            run_id=str(run.id),
            score=readiness_score,
            status=status.value,
        )
        return pre_audit

    async def _build_document_excerpts(self, project_id) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DataSource).where(
                DataSource.project_id == project_id,
                DataSource.source_type == SourceTypeEnum.document,
            )
        )
        excerpts = []
        for ds in result.scalars().all():
            file_upload_id = ds.raw_data.get("file_upload_id")
            if not file_upload_id:
                continue
            upload = await self.db.get(FileUpload, file_upload_id)
            if not upload or not upload.s3_key:
                continue
            try:
                content = await fetch_s3_bytes(upload.s3_key, upload.s3_bucket)
                text = await extract_text_async(content, upload.mime_type)
                excerpts.append({
                    "document_type": ds.raw_data.get("document_type", "unknown"),
                    "text": text[:MAX_TEXT_CHARS_PER_DOC],
                })
            except Exception as exc:
                logger.warning("pre_audit_text_extraction_failed", file_upload_id=file_upload_id, error=str(exc))
        return excerpts

    def _parse_run_output(self, output_data: Dict[str, Any]) -> Dict[str, Any]:
        ai_step = output_data.get("ai_evaluation", {})
        if isinstance(ai_step, dict):
            gaps = ai_step.get("gaps")
            risk_flags = ai_step.get("risk_flags")
            reasoning = ai_step.get("reasoning", "")

            # The AiEvaluationExecutor returns score/passed/reasoning/recommendation.
            # If the prompt produced extra keys (gaps, risk_flags), parse them from
            # the raw_response JSON as a fallback.
            if gaps is None or risk_flags is None:
                raw_response = ai_step.get("raw_response", "")
                if raw_response:
                    try:
                        parsed_raw = json.loads(raw_response)
                        if gaps is None:
                            gaps = parsed_raw.get("gaps")
                        if risk_flags is None:
                            risk_flags = parsed_raw.get("risk_flags")
                    except json.JSONDecodeError:
                        pass

            if gaps is None:
                gaps = self._extract_gaps(reasoning)
            if risk_flags is None:
                risk_flags = []

            return {
                "score": float(ai_step.get("score", 0.0)),
                "passed": bool(ai_step.get("passed", False)),
                "gaps": gaps,
                "risk_flags": risk_flags,
                "recommendation": ai_step.get("recommendation", ""),
                "reasoning": reasoning,
            }
        return {"score": 0.0, "passed": False, "gaps": [], "risk_flags": [], "recommendation": "", "reasoning": ""}

    def _extract_gaps(self, reasoning: str) -> List[str]:
        gaps = []
        for line in reasoning.split("\n"):
            line = line.strip()
            if line.lower().startswith(("- gap", "* gap", "gap:")):
                gaps.append(line)
        return gaps

    def _status_from_score(self, score: float, passed: bool, risk_flags: List[str]) -> PreAuditStatusEnum:
        critical = any(f.lower().startswith("high") or "critical" in f.lower() for f in risk_flags)
        if score >= 0.8 and passed and not critical:
            return PreAuditStatusEnum.passed
        if score < 0.6 or critical:
            return PreAuditStatusEnum.failed
        return PreAuditStatusEnum.gaps
