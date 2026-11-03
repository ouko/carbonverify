"""ValidationAgent: data validation, additionality screening, and risk flags."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.agents.base import BLEND_FORMULA, AgentResult, BaseAgent
from app.core.logging import get_logger
from app.models import CalculationRun, DataSource, Project

logger = get_logger(__name__)

RED_FLAG_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "false_positives": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of flags that appear to be false positives, with a short justification",
        },
        "confirmed_flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "assessment": {"type": "string"},
    },
    "required": ["false_positives", "confirmed_flags"],
}

# Confidence is capped when red flags survive review (conservative bias).
RED_FLAG_CONFIDENCE_CAP = 0.9


class ValidationAgent(BaseAgent):
    """Agent that validates data sources and screens project additionality/risk.

    Combines per-source statistical validation with additionality screening
    from project metadata and a red-flag list (implausibly smooth activity
    data, negative leakage, missing baseline). An LLM reviews the red-flag
    list for false positives; surviving flags cap confidence at 0.9.
    """

    agent_type = "validation"

    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Run comprehensive validation plus risk screening for the project."""
        project_id = self.project_id

        project_result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        data_sources = result.scalars().all()

        if not project or not data_sources:
            return self._no_data_result(
                reasoning=(
                    f"No data sources to validate for this project "
                    f"(project found: {project is not None}). Confidence set to 0.6 "
                    "pending data delivery."
                ),
                evidence={"project_found": project is not None, "data_sources": len(data_sources)},
            )

        # 1. Per-source validation.
        validation_results = []
        outlier_count = 0
        gap_count = 0
        for ds in data_sources:
            checks = self._validate_source(ds)
            validation_results.append(checks)
            outlier_count += checks["outlier_count"]
            gap_count += checks["gap_count"]

        total_records = sum(r.get("record_count", 0) for r in validation_results)
        outlier_rate = outlier_count / total_records if total_records > 0 else 0
        gap_percentage = (gap_count / len(data_sources) * 100) if data_sources else 0

        outlier_confidence = max(0, 1.0 - (outlier_rate * 5))
        gap_confidence = max(0, 1.0 - (gap_percentage / 100))

        # 2. Additionality screening from project metadata.
        additionality = self._screen_additionality(project)

        # 3. Red-flag list.
        red_flags = await self._collect_red_flags(project, data_sources)

        # 4. LLM false-positive review of the red-flag list, optionally
        # enriched with methodology knowledge-base passages (Phase 5). The
        # enrichment is best-effort and silently skipped when the knowledge
        # base is unavailable or empty.
        llm_context: dict[str, Any] = {
            "project": {
                "name": project.name,
                "methodology": project.methodology.value,
                "crediting_period_start": str(project.crediting_period_start),
                "crediting_period_end": str(project.crediting_period_end),
                "complexity_score": project.complexity_score,
            },
            "red_flags": red_flags,
        }
        knowledge = await self._knowledge_passages(
            (
                f"{project.methodology.value} methodology validation "
                "additionality requirements"
            ),
            registry=self._methodology_registry(project.methodology.value),
        )
        if knowledge:
            llm_context["methodology_knowledge"] = [
                {
                    "methodology_id": item["document"]["methodology_id"],
                    "title": item["document"]["title"],
                    "passage": item["chunk"]["content"][:800],
                }
                for item in knowledge
            ]

        llm_review = await self.reason_with_llm(
            task_prompt=(
                "Review this red-flag list for a carbon credit project. Identify "
                "false positives (flags that are expected or benign for this kind "
                "of project) and confirm the rest."
            ),
            context=llm_context,
            response_schema=RED_FLAG_REVIEW_SCHEMA,
        )
        confirmed_flags = red_flags
        false_positive_ids: list[str] = []
        if not llm_review.get("_fallback"):
            raw = llm_review.get("false_positives")
            if isinstance(raw, list):
                for item in raw:
                    false_positive_ids.append(str(item))
                confirmed_flags = [
                    f for f in red_flags
                    if f["id"] not in false_positive_ids and f["detail"] not in false_positive_ids
                ]

        heuristic = (outlier_confidence * 0.4) + (gap_confidence * 0.3) + (additionality["score"] * 0.3)
        heuristic = max(0.0, min(1.0, heuristic))

        llm_score: float | None = None
        if not llm_review.get("_fallback"):
            confirmed = llm_review.get("confirmed_flags")
            if isinstance(confirmed, list) and red_flags:
                llm_score = max(0.0, min(1.0, 1.0 - (len(confirmed) / max(1, len(red_flags))) * 0.5))
            else:
                llm_score = 1.0

        confidence = self.blend_confidence(heuristic, llm_score)

        # Conservative bias: surviving red flags cap confidence at 0.9.
        capped = False
        if confirmed_flags:
            confidence = min(confidence, RED_FLAG_CONFIDENCE_CAP)
            capped = True

        blend_note = (
            f"Blended heuristic ({heuristic:.2f}) with LLM flag review ({llm_score:.2f}) via {BLEND_FORMULA}."
            if llm_score is not None
            else f"LLM review unavailable; heuristic score stands alone (blending {BLEND_FORMULA} not applied)."
        )

        red_flag_summary = "; ".join(f["detail"] for f in confirmed_flags[:5]) if confirmed_flags else "none"
        reasoning = (
            f"Validated {len(data_sources)} source(s), {total_records} record(s): "
            f"outlier rate {outlier_rate:.1%}, gap rate {gap_percentage:.0f}%. "
            f"Additionality screen: {additionality['summary']} (score {additionality['score']:.2f}). "
            f"Red flags: {len(red_flags)} raised, {len(false_positive_ids)} dismissed as false "
            f"positive(s) by LLM review; surviving: {red_flag_summary}. "
            f"{blend_note}"
            + (f" Confidence capped at {RED_FLAG_CONFIDENCE_CAP} due to surviving red flags." if capped else "")
        )

        evidence = {
            "total_sources": len(data_sources),
            "total_records": total_records,
            "outlier_count": outlier_count,
            "outlier_rate": round(outlier_rate, 4),
            "gap_count": gap_count,
            "gap_percentage": round(gap_percentage, 2),
            "additionality": additionality,
            "red_flags_raised": red_flags,
            "red_flags_confirmed": confirmed_flags,
            "false_positive_ids": false_positive_ids,
            "confidence_capped": capped,
            "validation_results": validation_results,
        }

        output = self.build_output(
            reasoning,
            evidence,
            total_sources=len(data_sources),
            total_records=total_records,
            outlier_rate=round(outlier_rate, 4),
            gap_percentage=round(gap_percentage, 2),
            additionality=additionality,
            red_flags=confirmed_flags,
            false_positives_dismissed=len(false_positive_ids),
        )

        status = "completed" if outlier_rate < 0.05 and gap_percentage < 10 and not confirmed_flags else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )

    # ─── Screening helpers ────────────────────────────────────────────────

    @staticmethod
    def _methodology_registry(methodology: str) -> str:
        """Map a project methodology to its source registry for KB lookups."""
        if "TPDD" in methodology or "AMS" in methodology:
            return "gold_standard"
        return "verra"

    async def _knowledge_passages(
        self, question: str, registry: str | None = None
    ) -> list[dict[str, Any]]:
        """Best-effort knowledge-base enrichment; never breaks the agent.

        Silently returns [] when the knowledge base is not importable, errors,
        or has no ingested documents.
        """
        if self.db is None:
            return []
        try:
            from app.knowledge.service import KnowledgeBaseService

            return await KnowledgeBaseService(self.db).search(question, registry=registry, k=3)
        except Exception as exc:  # noqa: BLE001 — enrichment must never break the agent
            logger.debug("knowledge_enrichment_unavailable", agent_type=self.agent_type, error=str(exc))
            return []

    def _validate_source(self, ds: DataSource) -> dict[str, Any]:
        """Validate a single data source from its real processed data."""
        processed = ds.processed_data or {}
        records = processed.get("records_extracted", 0) or 0
        fields_mapped = processed.get("fields_mapped", 0) or 0

        # Outlier heuristic: implausibly high record counts for a single source.
        outliers = 0
        if isinstance(records, (int, float)) and records > 100000:
            outliers = 1
        # Gap heuristic: sources that mapped almost no fields are incomplete.
        gaps = 1 if fields_mapped and fields_mapped < 5 else 0

        # GPS boundary check on stored coordinates, when present.
        gps_valid = True
        gps = processed.get("gps")
        if isinstance(gps, dict):
            lat, lon = gps.get("latitude"), gps.get("longitude")
            if lat is not None and not (-90 <= lat <= 90):
                gps_valid = False
            if lon is not None and not (-180 <= lon <= 180):
                gps_valid = False

        return {
            "source_id": str(ds.id),
            "source_type": ds.source_type.value,
            "record_count": records,
            "fields_mapped": fields_mapped,
            "outlier_count": outliers,
            "gap_count": gaps,
            "gps_valid": gps_valid,
        }

    @staticmethod
    def _screen_additionality(project: Project) -> dict[str, Any]:
        """Screen additionality from project metadata (conservative pass/fail signals)."""
        checks = []
        now = datetime.now(UTC).date()

        start = project.crediting_period_start
        end = project.crediting_period_end
        period_valid = start is not None and end is not None and start < end
        checks.append({
            "check": "crediting_period_order",
            "passed": period_valid,
            "detail": f"Crediting period {start} → {end}",
        })
        not_future = start is not None and start <= now
        checks.append({
            "check": "crediting_period_started",
            "passed": not_future,
            "detail": f"Crediting period start {start} is {'in the future' if not not_future else 'in the past'}",
        })
        methodology_supported = project.methodology.value in ("TPDDTEC_v4", "VM0050", "VMR0006", "AMS-II.G")
        checks.append({
            "check": "methodology_supported",
            "passed": methodology_supported,
            "detail": f"Methodology {project.methodology.value}",
        })
        has_complexity = project.complexity_score is not None
        checks.append({
            "check": "site_characterization_present",
            "passed": has_complexity,
            "detail": "complexity_score present" if has_complexity else "complexity_score missing (site characterization incomplete)",
        })

        passed = sum(1 for c in checks if c["passed"])
        score = passed / len(checks)
        return {
            "score": round(score, 3),
            "checks": checks,
            "summary": f"{passed}/{len(checks)} additionality checks passed",
        }

    async def _collect_red_flags(
        self,
        project: Project,
        data_sources: list[DataSource],
    ) -> list[dict[str, Any]]:
        """Collect conservative red flags over project data."""
        flags: list[dict[str, Any]] = []

        # Activity data implausibly smooth: identical record counts across sources.
        record_counts = [
            (ds.processed_data or {}).get("records_extracted")
            for ds in data_sources
            if (ds.processed_data or {}).get("records_extracted")
        ]
        if len(record_counts) >= 3 and len(set(record_counts)) == 1:
            flags.append({
                "id": "smooth_activity_data",
                "detail": (
                    f"All {len(record_counts)} sources report identical record count "
                    f"{record_counts[0]} — activity data implausibly smooth"
                ),
            })

        calc_result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(1)
        )
        latest_calc = calc_result.scalar_one_or_none()

        # Missing baseline.
        if latest_calc is None:
            flags.append({
                "id": "missing_baseline",
                "detail": "No calculation run exists — baseline emissions not established",
            })
        else:
            leakage = (latest_calc.leakage_assessment or {}).get("total_leakage_tco2e", 0) or 0
            if leakage < 0:
                flags.append({
                    "id": "negative_leakage",
                    "detail": f"Negative leakage {leakage:.2f} tCO2e is physically implausible",
                })

        return flags
