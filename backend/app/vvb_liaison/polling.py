"""Registry polling and status tracking system."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.vvb_liaison.registry_clients.verra import VerraRegistryClient
from app.vvb_liaison.registry_clients.gold_standard import GoldStandardRegistryClient
from app.vvb_liaison.registry_clients.kenya_national import KenyaNationalRegistryClient
from app.core.logging import get_logger

logger = get_logger(__name__)

# Follow-up thresholds
FOLLOW_UP_DAYS = 14
ESCALATION_DAYS = 30


class RegistryPoller:
    """Polls multiple registries for project status updates."""
    
    def __init__(
        self,
        verra_api_key: Optional[str] = None,
        gs_api_key: Optional[str] = None,
        kenya_api_key: Optional[str] = None,
    ):
        self.clients = {
            "verra": VerraRegistryClient(api_key=verra_api_key),
            "gold_standard": GoldStandardRegistryClient(api_key=gs_api_key),
            "kenya_national": KenyaNationalRegistryClient(api_key=kenya_api_key),
        }
    
    def poll_project(self, registry: str, project_id: str) -> Dict[str, Any]:
        """Poll a single registry for project status."""
        client = self.clients.get(registry)
        if not client:
            return {"success": False, "error": f"Unknown registry: {registry}"}
        
        return client.get_project_status(project_id)
    
    def poll_all_registries(self, project_registrations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Poll all registered projects across all registries.
        
        Args:
            project_registrations: List of dicts with keys: registry, project_id, last_status
        """
        results = []
        
        for reg in project_registrations:
            registry = reg.get("registry")
            project_id = reg.get("project_id")
            last_status = reg.get("last_status")
            
            logger.info("polling_project", registry=registry, project_id=project_id)
            
            result = self.poll_project(registry, project_id)
            result["project_id"] = project_id
            result["registry"] = registry
            result["previous_status"] = last_status
            result["polled_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # Detect status changes
            if result.get("success"):
                new_status = result.get("verification_status") or result.get("project_status")
                if new_status != last_status:
                    result["status_changed"] = True
                    result["status_change"] = {
                        "from": last_status,
                        "to": new_status,
                    }
                    logger.info(
                        "status_change_detected",
                        registry=registry,
                        project_id=project_id,
                        from_status=last_status,
                        to_status=new_status,
                    )
                else:
                    result["status_changed"] = False
            
            results.append(result)
        
        return results
    
    def check_follow_up_needed(
        self,
        submission_date: datetime,
        current_status: str,
        last_follow_up: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Determine if a follow-up is needed based on elapsed time.
        
        Returns dict with action recommendation.
        """
        now = datetime.now(timezone.utc)
        days_pending = (now - submission_date).days
        
        # Don't follow up if already approved/rejected
        if current_status in ("approved", "verified", "rejected", "vvb_approved"):
            return {
                "action": "none",
                "reason": f"Status is final: {current_status}",
                "days_pending": days_pending,
            }
        
        # Check if already followed up recently
        if last_follow_up and (now - last_follow_up).days < 7:
            return {
                "action": "none",
                "reason": "Follow-up sent within last 7 days",
                "days_pending": days_pending,
                "days_since_last_follow_up": (now - last_follow_up).days,
            }
        
        if days_pending >= ESCALATION_DAYS:
            return {
                "action": "escalate",
                "reason": f"No response in {days_pending} days (escalation threshold: {ESCALATION_DAYS})",
                "days_pending": days_pending,
                "template": "escalation_email",
                "urgency": "high",
            }
        elif days_pending >= FOLLOW_UP_DAYS:
            return {
                "action": "follow_up",
                "reason": f"No response in {days_pending} days (follow-up threshold: {FOLLOW_UP_DAYS})",
                "days_pending": days_pending,
                "template": "submission_follow_up",
                "urgency": "medium",
            }
        
        return {
            "action": "wait",
            "reason": f"Only {days_pending} days pending (follow-up at {FOLLOW_UP_DAYS} days)",
            "days_pending": days_pending,
        }
    
    def close(self):
        """Close all registry clients."""
        for client in self.clients.values():
            client.close()


def generate_follow_up_email(
    project_name: str,
    registry_name: str,
    report_id: str,
    current_status: str,
    days_pending: int,
    emissions_reduction: float,
    monitoring_period_start: str,
    monitoring_period_end: str,
    methodology: str,
    compliance_score: float,
) -> Dict[str, Any]:
    """Generate follow-up email content."""
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    
    template_dir = Path(__file__).parent / "email_templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("submission_follow_up.html")
    
    html = template.render(
        project_name=project_name,
        registry_name=registry_name,
        report_id=report_id,
        current_status=current_status,
        days_pending=days_pending,
        emissions_reduction=round(emissions_reduction, 1),
        monitoring_period_start=monitoring_period_start,
        monitoring_period_end=monitoring_period_end,
        methodology=methodology,
        compliance_score=compliance_score,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        cv_version="1.1.0",
    )
    
    subject = f"Follow-up: Monitoring Report for {project_name} ({report_id})"
    
    return {
        "subject": subject,
        "html_body": html,
        "plain_text": f"Follow-up regarding monitoring report {report_id} for {project_name}. "
                      f"Status: {current_status}, pending for {days_pending} days.",
    }
