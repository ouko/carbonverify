"""Kimi API integration for NLP tasks in CarbonVerify."""

import os
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

KIMI_API_BASE = "https://api.moonshot.cn/v1"
DEFAULT_MODEL = "moonshot-v1-8k"


class KimiAPIClient:
    """Client for Kimi API (Moonshot AI) providing NLP capabilities."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIMI_API_KEY", "")
        self.base_url = KIMI_API_BASE
        self.model = DEFAULT_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send a chat completion request to Kimi API."""
        if not self.api_key:
            logger.warning("kimi_api_key_missing")
            return self._fallback_response(messages)

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }
        except Exception as exc:
            logger.error("kimi_api_error", error=str(exc))
            return self._fallback_response(messages)

    def _fallback_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate a fallback response when API is unavailable."""
        last_message = messages[-1]["content"] if messages else ""
        return {
            "success": False,
            "content": f"[Kimi API unavailable — fallback] Based on your query: '{last_message[:100]}...' Please review the methodology documentation directly.",
            "usage": {},
        }

    # ─── Specialized Methods ──────────────────────────────────────────────────

    async def draft_vvb_response(
        self,
        query_text: str,
        project_data: Dict[str, Any],
        methodology_kb: Optional[str] = None,
    ) -> str:
        """Draft a response to VVB clarification query."""
        system_prompt = (
            "You are a carbon credit verification expert. Draft a professional, "
            "technically accurate response to a VVB (Validation/Verification Body) query. "
            "Cite relevant methodology sections and IPCC guidelines where applicable."
        )
        user_prompt = f"""VVB Query: {query_text}

Project Information:
- Name: {project_data.get('name', 'N/A')}
- Methodology: {project_data.get('methodology', 'N/A')}
- Status: {project_data.get('status', 'N/A')}
- Emissions Reduction: {project_data.get('emissions_reduction', 'N/A')} tCO2e

Methodology Context:
{methodology_kb or 'Standard methodology guidelines apply.'}

Please draft a comprehensive, professional response addressing the VVB query with appropriate citations."""

        result = await self.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        return result["content"]

    async def generate_executive_summary(
        self,
        project_data: Dict[str, Any],
        calculation_results: Dict[str, Any],
    ) -> str:
        """Generate an executive summary for a monitoring report."""
        system_prompt = (
            "You are a carbon credit MRV expert. Write a concise, professional "
            "executive summary for a carbon credit monitoring report. Highlight key "
            "findings, emissions reductions, uncertainty, and compliance status."
        )
        user_prompt = f"""Generate an executive summary for the following project:

Project: {project_data.get('name', 'N/A')}
Methodology: {project_data.get('methodology', 'N/A')}
Monitoring Period: {project_data.get('monitoring_period', 'N/A')}

Key Results:
- Emissions Reduction: {calculation_results.get('emissions_reduction_tco2e', 'N/A')} tCO2e
- fNRB: {calculation_results.get('fnrb', 'N/A')}
- Uncertainty (95% CI): ±{calculation_results.get('uncertainty_95ci', 'N/A')} tCO2e
- Methodology Compliance: {calculation_results.get('methodology_compliance_score', 'N/A')}%
- Leakage: {calculation_results.get('leakage_tco2e', 'N/A')} tCO2e

Write 2-3 paragraphs suitable for a monitoring report executive summary."""

        result = await self.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], temperature=0.4, max_tokens=1024)
        return result["content"]

    async def answer_methodology_question(
        self,
        question: str,
        methodology: str,
        context_documents: Optional[List[str]] = None,
    ) -> str:
        """Answer methodology questions using RAG from vector database context."""
        system_prompt = (
            f"You are an expert on the {methodology} carbon credit methodology. "
            "Answer questions accurately, citing specific sections where possible. "
            "If uncertain, acknowledge limitations rather than hallucinating."
        )

        docs_context = ""
        if context_documents:
            docs_context = "\n\nRelevant methodology excerpts:\n" + "\n---\n".join(context_documents[:5])

        user_prompt = f"""Question: {question}

Methodology: {methodology}
{docs_context}

Provide a clear, accurate answer with citations to methodology sections."""

        result = await self.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], temperature=0.2, max_tokens=1536)
        return result["content"]

    async def explain_anomaly(
        self,
        data_point: Dict[str, Any],
        historical_context: Optional[List[Dict[str, Any]]] = None,
        field_name: str = "value",
    ) -> str:
        """Generate a natural language explanation of why a data point is anomalous."""
        system_prompt = (
            "You are a data quality analyst specializing in carbon credit MRV data. "
            "Explain anomalies in clear, actionable language that operators can understand "
            "and act upon. Suggest likely causes and remediation steps."
        )

        historical_str = ""
        if historical_context:
            values = [str(h.get(field_name, "N/A")) for h in historical_context[-10:]]
            historical_str = f"\nHistorical {field_name} values: {', '.join(values)}"

        user_prompt = f"""The following data point was flagged as anomalous:

Data Point: {data_point}
Field: {field_name}{historical_str}

Explain why this data point is anomalous and suggest:
1. Likely causes
2. Whether this is a data entry error or a real phenomenon
3. Recommended next steps

Keep the explanation concise (3-5 sentences)."""

        result = await self.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], temperature=0.3, max_tokens=512)
        return result["content"]

    async def generate_clarification_email(
        self,
        recipient: str,
        subject_context: str,
        key_points: List[str],
        tone: str = "professional",
    ) -> str:
        """Draft a clarification or follow-up email."""
        system_prompt = (
            f"You are writing a {tone} email for a carbon credit verification project. "
            "Be clear, concise, and maintain appropriate professional tone."
        )
        user_prompt = f"""Draft an email to: {recipient}

Subject Context: {subject_context}

Key points to include:
{chr(10).join(f'- {p}' for p in key_points)}

Write the full email body."""

        result = await self.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], temperature=0.4, max_tokens=1024)
        return result["content"]


# Global singleton
_kimi_client: Optional[KimiAPIClient] = None


def get_kimi_client() -> KimiAPIClient:
    global _kimi_client
    if _kimi_client is None:
        _kimi_client = KimiAPIClient()
    return _kimi_client
