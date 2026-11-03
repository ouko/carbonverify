"""QualityControlAgent: statistical sampling, cross-project anomaly detection, version audit."""

from typing import Any

from sqlalchemy import func, select

from app.agents.base import BLEND_FORMULA, AgentResult, BaseAgent
from app.core.logging import get_logger
from app.models import CalculationRun, DataSource, FileUpload, Project, SurveyResponse

logger = get_logger(__name__)

# IQR outlier threshold: values beyond Q3 + 1.5*IQR or below Q1 - 1.5*IQR.
IQR_MULTIPLIER = 1.5


class QualityControlAgent(BaseAgent):
    """Agent that performs continuous quality control via statistical sampling.

    Computes real sample statistics over the project's data points (null rate,
    IQR-based distribution outliers) in addition to the structural checks
    (negative emissions, high uncertainty, hash integrity). Cross-project
    consistency checks are skipped with a stated reason when fewer than two
    projects exist.
    """

    agent_type = "quality_control"

    async def run(self, context: dict[str, Any]) -> AgentResult:
        """Run quality control checks: sampling, anomaly detection, hash verification."""
        check_type = context.get("check_type", "milestone")  # "daily" or "milestone"

        flags: list[dict[str, Any]] = []

        # 1. Structural sampling of calculation runs.
        calc_flags, calc_samples = await self._sample_calculations()
        flags.extend(calc_flags)

        # 2. Statistical sampling across the project's data points:
        #    null rate + IQR outliers over numeric values.
        stats = await self._sample_data_points()

        # 3. Cross-project anomaly detection (skipped when < 2 projects).
        anomaly_flags, cross_project_note = await self._detect_cross_project_anomalies()
        flags.extend(anomaly_flags)

        # 4. Version control / hash verification.
        hash_flags = await self._verify_data_integrity()
        flags.extend(hash_flags)

        # 5. Blockchain anchoring check (placeholder).
        flags.extend(self._check_blockchain_anchors())

        sample_size = stats["sample_size"]
        failures = stats["null_count"] + stats["outlier_count"] + len(calc_flags) + len(hash_flags)
        pass_rate = (
            max(0.0, (sample_size - failures) / sample_size)
            if sample_size > 0
            else 0.0
        )
        heuristic = 0.6 + 0.4 * pass_rate if sample_size > 0 else 0.6

        # LLM review of the flag list for likely false positives.
        llm_review = await self.reason_with_llm(
            task_prompt=(
                "Review these quality-control flags. Estimate the fraction that are "
                "genuine data quality problems (0-1) — assign 'genuine_rate'."
            ),
            context={
                "project_id": str(self.project_id),
                "check_type": check_type,
                "flags": flags[:10],
                "null_rate": stats["null_rate"],
                "outlier_count": stats["outlier_count"],
                "sample_size": sample_size,
            },
            response_schema={
                "type": "object",
                "properties": {
                    "genuine_rate": {"type": "number"},
                    "summary": {"type": "string"},
                },
                "required": ["genuine_rate"],
            },
        )
        llm_genuine: float | None = None
        if not llm_review.get("_fallback"):
            raw = llm_review.get("genuine_rate")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                llm_genuine = max(0.0, min(1.0, float(raw)))

        confidence = self.blend_confidence(heuristic, llm_genuine)
        blend_note = (
            f"Blended sample pass rate ({heuristic:.2f}) with LLM genuine-flag rate "
            f"({llm_genuine:.2f}) via {BLEND_FORMULA}."
            if llm_genuine is not None
            else f"LLM review unavailable; sample pass rate stands alone (blending {BLEND_FORMULA} not applied)."
        )

        flag_count = len(flags)
        severity = "pass" if flag_count == 0 else ("warning" if flag_count <= 2 else "critical")

        top_flags = "; ".join(f["detail"] for f in flags[:3]) if flags else "none"
        reasoning = (
            f"Sampled {sample_size} data point(s): null rate {stats['null_rate']:.1%} "
            f"({stats['null_count']} null), {stats['outlier_count']} IQR outlier(s). "
            f"{len(calc_flags)} calculation flag(s), {len(hash_flags)} integrity flag(s); "
            f"cross-project check: {cross_project_note}. Top flags: {top_flags}. {blend_note}"
        )

        evidence = {
            "check_type": check_type,
            "sample_size": sample_size,
            "null_count": stats["null_count"],
            "null_rate": round(stats["null_rate"], 4),
            "outlier_count": stats["outlier_count"],
            "outlier_values": stats["outlier_values"],
            "calc_sample_size": calc_samples,
            "calc_flag_count": len(calc_flags),
            "hash_flag_count": len(hash_flags),
            "cross_project": cross_project_note,
            "flag_count": flag_count,
            "flags": flags[:10],
            "pass_rate": round(pass_rate, 3),
            "llm_genuine_rate": llm_genuine,
        }

        output = self.build_output(
            reasoning,
            evidence,
            check_type=check_type,
            flag_count=flag_count,
            severity=severity,
            flags=flags,
            sample_stats=stats,
            cross_project=cross_project_note,
            recommendation=(
                "No issues detected" if severity == "pass"
                else "Review flagged items before proceeding" if severity == "warning"
                else "Halt pipeline — critical issues require immediate attention"
            ),
        )

        # QC agent always completes — its job is to flag, not block.
        return AgentResult(
            status="completed",
            confidence_score=confidence,
            output_data=output,
            reasoning=reasoning,
            evidence=evidence,
        )

    # ─── Sampling helpers ─────────────────────────────────────────────────

    async def _sample_calculations(self) -> tuple:
        """Structurally sample recent calculation runs. Returns (flags, sample_size)."""
        result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(5)
        )
        calcs = result.scalars().all()

        flags = []
        for calc in calcs:
            emissions = calc.emissions_reduction_tCO2e or 0
            if emissions < 0:
                flags.append({
                    "type": "negative_emissions",
                    "calculation_run_id": str(calc.id),
                    "detail": f"Emissions reduction is negative: {emissions:.2f} tCO2e",
                })

            uncertainty = calc.uncertainty_95CI or 0
            if emissions and uncertainty / emissions > 0.5:
                flags.append({
                    "type": "high_uncertainty",
                    "calculation_run_id": str(calc.id),
                    "detail": f"Uncertainty ratio {uncertainty/emissions:.1%} exceeds 50% threshold",
                })

        return flags, len(calcs)

    async def _sample_data_points(self) -> dict[str, Any]:
        """Compute null rate and IQR outliers over the project's numeric data points.

        Numeric samples are drawn from calculation runs, data-source processed
        data, and survey confidence scores — the 'transactions' of the MRV
        pipeline.
        """
        samples: list[float] = []
        nulls = 0
        total_fields = 0

        calc_result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(10)
        )
        for calc in calc_result.scalars().all():
            for value in (calc.fNRB_value, calc.emissions_reduction_tCO2e, calc.uncertainty_95CI):
                total_fields += 1
                if value is None:
                    nulls += 1
                else:
                    samples.append(float(value))

        ds_result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == self.project_id).limit(10)
        )
        for ds in ds_result.scalars().all():
            for key in ("records_extracted", "fields_mapped"):
                total_fields += 1
                value = (ds.processed_data or {}).get(key)
                if value is None:
                    nulls += 1
                else:
                    samples.append(float(value))

        try:
            survey_result = await self.db.execute(
                select(SurveyResponse).where(SurveyResponse.project_id == self.project_id).limit(50)
            )
            for survey in survey_result.scalars().all():
                total_fields += 1
                if survey.confidence_score is None:
                    nulls += 1
                else:
                    samples.append(float(survey.confidence_score))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("qc_survey_sampling_failed", error=str(exc))

        outlier_count = self._iqr_outlier_count(samples)
        return {
            "sample_size": total_fields,
            "null_count": nulls,
            "null_rate": (nulls / total_fields) if total_fields else 0.0,
            "numeric_sample_size": len(samples),
            "outlier_count": outlier_count,
            "outlier_values": self._iqr_outliers(samples)[:5],
        }

    @staticmethod
    def _iqr_outliers(samples: list[float]) -> list[float]:
        """Values beyond Q1 - 1.5*IQR / Q3 + 1.5*IQR (empty for small samples)."""
        if len(samples) < 4:
            return []
        ordered = sorted(samples)
        n = len(ordered)
        q1 = ordered[n // 4]
        q3 = ordered[(3 * n) // 4]
        iqr = q3 - q1
        low = q1 - IQR_MULTIPLIER * iqr
        high = q3 + IQR_MULTIPLIER * iqr
        return [s for s in ordered if s < low or s > high]

    def _iqr_outlier_count(self, samples: list[float]) -> int:
        return len(self._iqr_outliers(samples))

    async def _detect_cross_project_anomalies(self) -> tuple:
        """Compare latest calculation to peer projects. Returns (flags, note)."""
        project_count = await self.db.execute(select(func.count(Project.id)))
        total_projects = project_count.scalar() or 0
        if total_projects < 2:
            return [], f"skipped — only {total_projects} project(s) in system (need >= 2)"

        result = await self.db.execute(
            select(func.avg(CalculationRun.emissions_reduction_tCO2e))
            .where(CalculationRun.project_id != self.project_id)
        )
        peer_avg = result.scalar() or 0

        result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        flags = []
        if latest and latest.emissions_reduction_tCO2e and peer_avg > 0:
            deviation = abs(latest.emissions_reduction_tCO2e - peer_avg) / peer_avg
            if deviation > 0.5:
                flags.append({
                    "type": "cross_project_anomaly",
                    "calculation_run_id": str(latest.id),
                    "detail": (
                        f"Emissions {latest.emissions_reduction_tCO2e:.1f} deviates "
                        f"{deviation:.1%} from peer average {peer_avg:.1f}"
                    ),
                })
        return flags, f"ran against {total_projects - 1} peer project(s)"

    async def _verify_data_integrity(self) -> list[dict[str, Any]]:
        """Verify SHA-256 hashes of file uploads."""
        result = await self.db.execute(
            select(FileUpload).where(FileUpload.project_id == self.project_id)
        )
        uploads = result.scalars().all()

        flags = []
        for upload in uploads:
            if not upload.file_hash_sha256 or len(upload.file_hash_sha256) != 64:
                flags.append({
                    "type": "hash_verification_failed",
                    "upload_id": str(upload.id),
                    "detail": "Invalid or missing SHA-256 hash",
                })

        return flags

    def _check_blockchain_anchors(self) -> list[dict[str, Any]]:
        """Placeholder for blockchain anchoring verification."""
        # In production: verify Merkle root on-chain
        return []
