"""Gold Standard Registry API client."""

from typing import Dict, Any, Optional

from app.vvb_liaison.registry_clients.base import BaseRegistryClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class GoldStandardRegistryClient(BaseRegistryClient):
    """Client for Gold Standard Registry API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.goldstandard.org/v1",
    ):
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            max_retries=3,
            retry_delay=2.0,
        )
    
    async def submit_monitoring_report(
        self,
        project_id: str,
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit TPDDTEC monitoring report to Gold Standard."""
        logger.info("submitting_gs_monitoring_report", project_id=project_id)
        
        payload = {
            "project_id": project_id,
            "report_type": "monitoring_report",
            "monitoring_period": {
                "start": report_data.get("monitoring_period_start"),
                "end": report_data.get("monitoring_period_end"),
            },
            "emission_reductions": {
                "gross_tco2e": report_data.get("gross_reduction_tco2e"),
                "net_tco2e": report_data.get("emissions_reduction_tco2e"),
                "uncertainty_95ci": report_data.get("uncertainty_95CI"),
            },
            "methodology": report_data.get("methodology", "TPDDTEC_v4"),
            "verification_body": report_data.get("vvb_name"),
            "documents": [
                {
                    "type": "monitoring_report",
                    "url": doc.get("url"),
                    "checksum": doc.get("checksum"),
                }
                for doc in report_data.get("documents", [])
            ],
        }
        
        try:
            result = await self.post(f"/projects/{project_id}/verification", json_data=payload)
            logger.info("gs_report_submitted", project_id=project_id, verification_id=result.get("verification_id"))
            return {
                "success": True,
                "registry": "gold_standard",
                "verification_id": result.get("verification_id"),
                "status": result.get("status", "pending_review"),
                "submitted_at": result.get("submitted_at"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("gs_submission_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "gold_standard",
                "error": str(e),
                "status": "failed",
            }
    
    async def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get current project status from Gold Standard."""
        logger.info("polling_gs_project", project_id=project_id)
        
        try:
            result = await self.get(f"/projects/{project_id}")
            return {
                "success": True,
                "registry": "gold_standard",
                "project_status": result.get("status"),
                "verification_status": result.get("verification_status"),
                "certified_credits": result.get("certified_credits", 0),
                "pending_credits": result.get("pending_credits", 0),
                "last_updated": result.get("updated_at"),
                "raw_response": result,
            }
        except Exception as e:
            logger.error("gs_polling_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "gold_standard",
                "error": str(e),
            }
    
    async def get_verification_history(self, project_id: str) -> Dict[str, Any]:
        """Get verification history from Gold Standard."""
        try:
            result = await self.get(f"/projects/{project_id}/verification-history")
            return {
                "success": True,
                "registry": "gold_standard",
                "history": result.get("verification_history", []),
            }
        except Exception as e:
            logger.error("gs_history_failed", project_id=project_id, error=str(e))
            return {
                "success": False,
                "registry": "gold_standard",
                "error": str(e),
            }
