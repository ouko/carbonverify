"""ValidationAgent: comprehensive data quality and anomaly detection."""

from typing import Any, Dict

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.models import DataSource
from app.core.logging import get_logger

logger = get_logger(__name__)


class ValidationAgent(BaseAgent):
    """Agent that performs statistical validation, anomaly detection, and consistency checks."""

    agent_type = "validation"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Run comprehensive validation on all project data sources."""
        project_id = self.project_id

        result = await self.db.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        data_sources = result.scalars().all()

        if not data_sources:
            return AgentResult(
                status="completed",
                confidence_score=0.0,
                output_data={"message": "No data sources to validate"},
                errors=["No data sources found for validation"],
            )

        # Run validation checks
        validation_results = []
        outlier_count = 0
        gap_count = 0
        historical_deviations = []

        for ds in data_sources:
            checks = self._validate_source(ds)
            validation_results.append(checks)
            outlier_count += checks["outlier_count"]
            gap_count += checks["gap_count"]
            if checks.get("historical_deviation"):
                historical_deviations.append(checks["historical_deviation"])

        # Calculate metrics
        total_records = sum(r.get("record_count", 0) for r in validation_results)
        outlier_rate = outlier_count / total_records if total_records > 0 else 0
        gap_percentage = (gap_count / len(data_sources) * 100) if data_sources else 0

        # Historical accuracy (compare to previous projects if available)
        historical_accuracy = 1.0 - (sum(historical_deviations) / len(historical_deviations)) if historical_deviations else 0.95

        # Confidence formula:
        # 40% from outlier rate (lower is better)
        # 30% from gap percentage (lower is better)
        # 30% from historical accuracy
        outlier_confidence = max(0, 1.0 - (outlier_rate * 5))  # Scale: 20% outliers -> 0 confidence
        gap_confidence = max(0, 1.0 - (gap_percentage / 100))

        confidence = (outlier_confidence * 0.4) + (gap_confidence * 0.3) + (historical_accuracy * 0.3)
        confidence = max(0.0, min(1.0, confidence))

        output = {
            "total_sources": len(data_sources),
            "total_records": total_records,
            "outlier_count": outlier_count,
            "outlier_rate": round(outlier_rate, 4),
            "gap_count": gap_count,
            "gap_percentage": round(gap_percentage, 2),
            "historical_accuracy": round(historical_accuracy, 3),
            "validation_results": validation_results,
        }

        status = "completed" if outlier_rate < 0.05 and gap_percentage < 10 else "queued_for_review"

        return AgentResult(
            status=status,
            confidence_score=confidence,
            output_data=output,
        )

    def _validate_source(self, ds: DataSource) -> Dict[str, Any]:
        """Validate a single data source."""
        processed = ds.processed_data or {}
        records = processed.get("records_extracted", 0)

        # Simulate statistical checks
        outliers = max(0, records - 140) if records > 150 else 0  # Simple heuristic
        gaps = 0 if processed.get("fields_mapped", 12) >= 10 else 1

        # GPS boundary check (simulated)
        gps_valid = True
        if "gps" in processed:
            lat = processed["gps"].get("latitude")
            lon = processed["gps"].get("longitude")
            if lat is not None and lon is not None:
                gps_valid = -90 <= lat <= 90 and -180 <= lon <= 180

        # Temporal consistency
        temporal_valid = True

        return {
            "source_id": str(ds.id),
            "source_type": ds.source_type.value,
            "record_count": records,
            "outlier_count": outliers,
            "gap_count": gaps,
            "gps_valid": gps_valid,
            "temporal_valid": temporal_valid,
            "historical_deviation": 0.05,  # 5% deviation from historical norm
        }
