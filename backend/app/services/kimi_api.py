"""Kimi API integration for NLP tasks in CarbonVerify."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger
from app.core.circuit_breaker import with_circuit_breaker
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_MODEL = "moonshot-v1-8k"

AGENT_SYSTEM_PROMPT = (
    "You are a CarbonVerify MRV (Monitoring, Reporting, Verification) agent. "
    "Be conservative: only assert what the evidence supports, cite the specific "
    "facts you rely on, and acknowledge uncertainty rather than guessing. "
    "When a structured result is requested, output strict JSON matching the "
    "requested schema exactly."
)


@dataclass
class ToolCall:
    """A single tool call requested by the model."""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallResult:
    """Parsed result of a chat completion that may include tool calls."""

    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    raw: Dict[str, Any] = field(default_factory=dict)


class KimiAPIClient:
    """Client for Kimi API (Moonshot AI) providing NLP capabilities."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY", "")
        self.base_url = settings.KIMI_API_BASE
        self.model = settings.KIMI_MODEL or DEFAULT_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)

    @with_circuit_breaker("kimi_api")
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

    @with_circuit_breaker("kimi_api")
    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tool_choice: Any = "auto",
    ) -> ToolCallResult:
        """Send a chat completion request with tool-calling support.

        Uses the OpenAI-compatible ``tools`` / ``tool_choice`` parameters and
        parses any requested tool calls from the response. Falls back to an
        empty result when no API key is configured or the request fails.
        """
        if not self.api_key:
            logger.warning("kimi_api_key_missing")
            return ToolCallResult(content=None, finish_reason="fallback")

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model or self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice.get("message", {}) or {}
            tool_calls = []
            for tc in message.get("tool_calls") or []:
                function = tc.get("function", {}) or {}
                arguments: Dict[str, Any] = {}
                raw_args = function.get("arguments")
                if isinstance(raw_args, dict):
                    arguments = raw_args
                elif isinstance(raw_args, str) and raw_args.strip():
                    try:
                        parsed = json.loads(raw_args)
                        arguments = parsed if isinstance(parsed, dict) else {"value": parsed}
                    except (ValueError, TypeError):
                        logger.warning("kimi_tool_arguments_parse_failed", raw=raw_args[:200])
                        arguments = {}
                tool_calls.append(ToolCall(name=function.get("name", ""), arguments=arguments))

            return ToolCallResult(
                content=message.get("content"),
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop"),
                raw=data,
            )
        except Exception as exc:
            logger.error("kimi_api_tool_error", error=str(exc))
            return ToolCallResult(content=None, finish_reason="error", raw={"error": str(exc)})

    async def reason(
        self,
        prompt: str,
        context: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Agent-facing structured reasoning helper.

        Builds a conservative MRV-agent conversation from ``prompt`` +
        ``context``. When ``response_schema`` is given, the model is forced to
        call a ``submit_result`` tool whose parameters are the schema, and the
        parsed arguments are returned as a dict. When no API key is configured
        (or the call fails), returns a deterministic local heuristic result
        flagged ``{"_fallback": True}`` so callers never block on the network.
        """
        user_content = prompt
        if context:
            user_content += "\n\nContext (JSON):\n" + json.dumps(context, default=str, indent=2)

        all_tools = list(tools or [])
        if response_schema is not None:
            all_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "submit_result",
                        "description": "Submit the structured analysis result.",
                        "parameters": response_schema,
                    },
                }
            )

        if not self.api_key:
            return self._fallback_reasoning(prompt, context, response_schema)

        result = await self.chat_with_tools(
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            tools=all_tools,
            model=model,
            max_tokens=max_tokens,
            tool_choice=(
                {"type": "function", "function": {"name": "submit_result"}}
                if response_schema is not None
                else "auto"
            ),
        )

        for tool_call in result.tool_calls:
            if tool_call.name == "submit_result" and tool_call.arguments:
                return dict(tool_call.arguments)

        if result.content:
            try:
                parsed = json.loads(result.content)
                if isinstance(parsed, dict):
                    return parsed
            except ValueError:
                pass
            return {"_fallback": True, "summary": result.content[:500]}

        return self._fallback_reasoning(prompt, context, response_schema)

    def _fallback_reasoning(
        self,
        prompt: str,
        context: Dict[str, Any],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic local heuristic used when the Kimi API is unavailable."""
        fallback: Dict[str, Any] = {
            "_fallback": True,
            "reason": "Kimi API unavailable — deterministic heuristic result",
            "task": prompt[:200],
            "context_keys": sorted(context.keys()) if isinstance(context, dict) else [],
        }
        if response_schema is not None:
            properties = response_schema.get("properties", {}) if isinstance(response_schema, dict) else {}
            for key in properties:
                if isinstance(properties[key], dict) and properties[key].get("type") == "number":
                    fallback[key] = 0.5
                elif isinstance(properties[key], dict) and properties[key].get("type") == "array":
                    fallback[key] = []
                else:
                    fallback[key] = ""
        return fallback

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
