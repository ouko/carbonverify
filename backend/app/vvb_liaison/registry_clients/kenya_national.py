"""Kenya National Carbon Registry API client."""

from typing import Dict, Any, Optional

from app.vvb_liaison.registry_clients.base import BaseRegistryClient
from app.core.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)


class KenyaNationalRegistryClient(BaseRegistryClient):
    """
    Client for Kenya National Carbon Registry.

    Kenya is developing its national carbon registry under the Climate Change Act.
    This client makes actual HTTP requests to the configured registry endpoint.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        settings = get_settings()
        resolved_base_url = base_url or settings.KENYA_NATIONAL_REGISTRY_BASE_URL
        resolved_api_key = api_key or getattr(settings, "KENYA_NATIONAL_REGISTRY_API_KEY", "")
        super().__init__(
            base_url=resolved_base_url or "https://api.kenyacarbonregistry.go.ke/v1",
            api_key=resolved_api_key,
            max_retries=3,
            retry_delay=2.0,
        )
        self._configured = bool(resolved_base_url)

    def _not_configured_response(self) -> Dict[str, Any]:
        return {
            "success": False,
            "registry": "kenya_national",
            "error": "Kenya National Carbon Registry is not configured. Set KENYA_NATIONAL_REGISTRY_BASE_URL.",
            "status": "not_configured",
        }

    async def submit_monitoring_report(
        self,
        project_id: str,
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit monitoring report to Kenya National Registry."""
        if not self._configured:
            return self._not_configured_response()

        logger.info("submitting_kenya_monitoring_report", project_id=project_id)

        payload = {
            "project_id": project_id,
            "report_type": "monitoring_report",
            "monitoring_period_start": report_data.get("monitoring_period_start"),
            "monitoring_period_end": report_data.get("monitoring_period_end"),
            "emission_reductions_tco2e": report_data.get("emissions_reduction_tco2e"),
            "methodology": report_data.get("methodology", "AMS-III.AR"),
            "documents": report_data.get("documents", []),
        }

        try:
            result = await self.post(f"/projects/{project_id}/monitoring-reports", json_data=payload)
            logger.info("kenya_report_submitted", project_id=project_id, report_id=result.get("id"))
            return {
                "success": True,
                "registry": "kenya_national",
                "report_id": result.get("id"),
                "status": result.get("status", "submitted"),
                "submitted_at": result.get("submitted_at"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("kenya_submission_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "kenya_national",
                "error": str(e),
                "status": "failed",
            }

    async def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get project status from Kenya National Registry."""
        if not self._configured:
            return self._not_configured_response()

        logger.info("polling_kenya_project", project_id=project_id)

        try:
            result = await self.get(f"/projects/{project_id}")
            return {
                "success": True,
                "registry": "kenya_national",
                "project_status": result.get("status"),
                "verification_status": result.get("verification_status"),
                "credits_issued": result.get("credits_issued", 0),
                "credits_pending": result.get("credits_pending", 0),
                "last_updated": result.get("last_updated"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("kenya_polling_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "kenya_national",
                "error": str(e),
            }

    async def get_verification_history(self, project_id: str) -> Dict[str, Any]:
        """Get verification history from Kenya National Registry."""
        if not self._configured:
            return self._not_configured_response()

        try:
            result = await self.get(f"/projects/{project_id}/verification-history")
            return {
                "success": True,
                "registry": "kenya_national",
                "history": result.get("history", []),
            }
        except Exception as e:
            logger.error("kenya_history_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "kenya_national",
                "error": str(e),
            }
