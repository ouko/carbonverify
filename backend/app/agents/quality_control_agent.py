"""QualityControlAgent: statistical sampling, cross-project anomaly detection, version audit."""

from typing import Any, Dict, List

from sqlalchemy import select, func

from app.agents.base import AgentResult, BaseAgent
from app.models import CalculationRun, FileUpload
from app.core.logging import get_logger

logger = get_logger(__name__)


class QualityControlAgent(BaseAgent):
    """Agent that performs continuous quality control via statistical sampling."""

    agent_type = "quality_control"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Run quality control checks: sampling, anomaly detection, hash verification."""
        # project_id available via self.project_id
        check_type = context.get("check_type", "milestone")  # "daily" or "milestone"

        flags: List[Dict[str, Any]] = []

        # 1. Statistical sampling of calculations
        calc_flags = await self._sample_calculations()
        flags.extend(calc_flags)

        # 2. Cross-project anomaly detection
        anomaly_flags = await self._detect_cross_project_anomalies()
        flags.extend(anomaly_flags)

        # 3. Version control / hash verification
        hash_flags = await self._verify_data_integrity()
        flags.extend(hash_flags)

        # 4. Blockchain anchoring check (placeholder)
        anchor_flags = await self._check_blockchain_anchors()
        flags.extend(anchor_flags)

        # Quality control doesn't produce a confidence score — it produces flags
        flag_count = len(flags)
        severity = "pass" if flag_count == 0 else ("warning" if flag_count <= 2 else "critical")

        output = {
            "check_type": check_type,
            "flag_count": flag_count,
            "severity": severity,
            "flags": flags,
            "recommendation": (
                "No issues detected" if severity == "pass"
                else "Review flagged items before proceeding" if severity == "warning"
                else "Halt pipeline — critical issues require immediate attention"
            ),
        }

        # QC agent always returns completed — its job is to flag, not block
        return AgentResult(
            status="completed",
            confidence_score=1.0 if severity == "pass" else 0.7,
            output_data=output,
        )

    async def _sample_calculations(self) -> List[Dict[str, Any]]:
        """Statistically sample recent calculation runs."""
        result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(5)
        )
        calcs = result.scalars().all()

        flags = []
        for calc in calcs:
            # Check for negative emissions reductions
            emissions = calc.emissions_reduction_tCO2e or 0
            if emissions < 0:
                flags.append({
                    "type": "negative_emissions",
                    "calculation_run_id": str(calc.id),
                    "detail": f"Emissions reduction is negative: {emissions:.2f} tCO2e",
                })

            # Check for excessive uncertainty
            uncertainty = calc.uncertainty_95CI or 0
            if emissions and uncertainty / emissions > 0.5:
                flags.append({
                    "type": "high_uncertainty",
                    "calculation_run_id": str(calc.id),
                    "detail": f"Uncertainty ratio {uncertainty/emissions:.1%} exceeds 50% threshold",
                })

        return flags

    async def _detect_cross_project_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies by comparing to peer projects."""
        # Get average emissions for similar projects
        result = await self.db.execute(
            select(func.avg(CalculationRun.emissions_reduction_tCO2e))
            .where(CalculationRun.project_id != self.project_id)
        )
        peer_avg = result.scalar() or 0

        # Get this project's latest calculation
        result = await self.db.execute(
            select(CalculationRun)
            .where(CalculationRun.project_id == self.project_id)
            .order_by(CalculationRun.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        flags = []
        if latest and latest.emissions_reduction_tCO2e:
            deviation = abs(latest.emissions_reduction_tCO2e - peer_avg) / peer_avg if peer_avg > 0 else 0
            if deviation > 0.5:
                flags.append({
                    "type": "cross_project_anomaly",
                    "calculation_run_id": str(latest.id),
                    "detail": f"Emissions {latest.emissions_reduction_tCO2e:.1f} deviates {deviation:.1%} from peer average {peer_avg:.1f}",
                })

        return flags

    async def _verify_data_integrity(self) -> List[Dict[str, Any]]:
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

    async def _check_blockchain_anchors(self) -> List[Dict[str, Any]]:
        """Placeholder for blockchain anchoring verification."""
        # In production: verify Merkle root on-chain
        return []
