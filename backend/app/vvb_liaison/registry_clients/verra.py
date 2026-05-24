"""Verra Project Hub API client."""

from typing import Dict, Any, Optional

from app.vvb_liaison.registry_clients.base import BaseRegistryClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class VerraRegistryClient(BaseRegistryClient):
    """Client for Verra Project Hub API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://registry.verra.org/api",
    ):
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            max_retries=3,
            retry_delay=2.0,
        )
    
    def submit_monitoring_report(
        self,
        project_id: str,
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit VM0050 monitoring report to Verra."""
        logger.info("submitting_verra_monitoring_report", project_id=project_id)
        
        payload = {
            "project_id": project_id,
            "report_type": "monitoring_report",
            "monitoring_period_start": report_data.get("monitoring_period_start"),
            "monitoring_period_end": report_data.get("monitoring_period_end"),
            "emission_reductions_tco2e": report_data.get("emissions_reduction_tco2e"),
            "uncertainty_95ci": report_data.get("uncertainty_95CI"),
            "methodology": report_data.get("methodology", "VM0050"),
            "calculation_version": "1.1.0",
            "documents": report_data.get("documents", []),
        }
        
        try:
            result = self.post(f"/projects/{project_id}/monitoring-reports", json_data=payload)
            logger.info("verra_report_submitted", project_id=project_id, report_id=result.get("id"))
            return {
                "success": True,
                "registry": "verra",
                "report_id": result.get("id"),
                "status": result.get("status", "submitted"),
                "submitted_at": result.get("submitted_at"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("verra_submission_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "verra",
                "error": str(e),
                "status": "failed",
            }
    
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get current project status from Verra."""
        logger.info("polling_verra_project", project_id=project_id)
        
        try:
            result = self.get(f"/projects/{project_id}")
            return {
                "success": True,
                "registry": "verra",
                "project_status": result.get("status"),
                "verification_status": result.get("verification_status"),
                "credits_issued": result.get("credits_issued", 0),
                "credits_pending": result.get("credits_pending", 0),
                "last_updated": result.get("last_updated"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("verra_polling_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "verra",
                "error": str(e),
            }
    
    def get_verification_history(self, project_id: str) -> Dict[str, Any]:
        """Get verification history from Verra."""
        try:
            result = self.get(f"/projects/{project_id}/verification-history")
            return {
                "success": True,
                "registry": "verra",
                "history": result.get("history", []),
            }
        except Exception as e:
            logger.error("verra_history_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "verra",
                "error": str(e),
            }
