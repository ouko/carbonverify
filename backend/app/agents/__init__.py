"""Kimi Claw multi-agent orchestration agents."""

from app.agents.base import AgentResult, BaseAgent
from app.agents.ingestion_agent import IngestionAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.calculation_agent import CalculationAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.vvb_liaison_agent import VVBLiaisonAgent
from app.agents.quality_control_agent import QualityControlAgent
from app.agents.client_success_agent import ClientSuccessAgent

AGENT_REGISTRY = {
    "ingestion": IngestionAgent,
    "validation": ValidationAgent,
    "calculation": CalculationAgent,
    "reporting": ReportingAgent,
    "vvb_liaison": VVBLiaisonAgent,
    "quality_control": QualityControlAgent,
    "client_success": ClientSuccessAgent,
}

__all__ = [
    "AgentResult",
    "BaseAgent",
    "IngestionAgent",
    "ValidationAgent",
    "CalculationAgent",
    "ReportingAgent",
    "VVBLiaisonAgent",
    "QualityControlAgent",
    "ClientSuccessAgent",
    "AGENT_REGISTRY",
]
