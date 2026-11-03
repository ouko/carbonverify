"""Kimi Claw multi-agent orchestration agents."""

from typing import Callable, Dict

from app.agents.base import AgentResult, BaseAgent
from app.agents.calculation_agent import CalculationAgent
from app.agents.client_success_agent import ClientSuccessAgent
from app.agents.ingestion_agent import IngestionAgent
from app.agents.quality_control_agent import QualityControlAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.vvb_liaison_agent import VVBLiaisonAgent

AGENT_REGISTRY: Dict[str, Callable[..., BaseAgent]] = {
    "ingestion": IngestionAgent,
    "validation": ValidationAgent,
    "calculation": CalculationAgent,
    "reporting": ReportingAgent,
    "vvb_liaison": VVBLiaisonAgent,
    "quality_control": QualityControlAgent,
    "client_success": ClientSuccessAgent,
}

__all__ = [
    "AGENT_REGISTRY",
    "AgentResult",
    "BaseAgent",
    "CalculationAgent",
    "ClientSuccessAgent",
    "IngestionAgent",
    "QualityControlAgent",
    "ReportingAgent",
    "VVBLiaisonAgent",
    "ValidationAgent",
]
