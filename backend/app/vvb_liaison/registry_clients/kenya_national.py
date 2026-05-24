"""Kenya National Carbon Registry API client (placeholder for future integration)."""

from typing import Dict, Any, Optional

from app.vvb_liaison.registry_clients.base import BaseRegistryClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class KenyaNationalRegistryClient(BaseRegistryClient):
    """
    Placeholder client for Kenya National Carbon Registry.
    
    Kenya is developing its national carbon registry under the Climate Change Act.
    This client is ready for integration once the API is publicly available.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.kenyacarbonregistry.go.ke/v1",
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
        """Submit monitoring report to Kenya National Registry."""
        logger.info("kenya_registry_placeholder", project_id=project_id)
        return {
            "success": False,
            "registry": "kenya_national",
            "error": "Kenya National Carbon Registry API not yet available",
            "status": "not_implemented",
            "note": "This registry is in development. Integration will be enabled once the API is published.",
        }
    
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get project status from Kenya National Registry."""
        return {
            "success": False,
            "registry": "kenya_national",
            "error": "Kenya National Carbon Registry API not yet available",
            "status": "not_implemented",
        }
    
    def get_verification_history(self, project_id: str) -> Dict[str, Any]:
        """Get verification history from Kenya National Registry."""
        return {
            "success": False,
            "registry": "kenya_national",
            "error": "Kenya National Carbon Registry API not yet available",
            "status": "not_implemented",
        }
