"""AI-driven custom methodology generation service."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.services.kimi_api import KimiAPIClient
from app.models import GeneratedMethodology, MethodologyVersion
from app.core.logging import get_logger

logger = get_logger(__name__)


class MethodologyGeneratorService:
    """Generates registry-aligned draft methodologies for unique projects."""

    def __init__(self, llm_client: Optional[KimiAPIClient] = None):
        self.llm = llm_client or KimiAPIClient()

    async def fetch_existing_methodologies(
        self, db: AsyncSession, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return recent methodology versions for gap analysis context."""
        result = await db.execute(
            select(MethodologyVersion)
            .order_by(desc(MethodologyVersion.effective_date))
            .limit(limit)
        )
        return [
            {
                "name": v.methodology_name,
                "version": v.version,
                "summary": v.change_summary or "",
                "rules": v.rules_json or {},
            }
            for v in result.scalars().all()
        ]

    async def analyze_gap(
        self,
        project_context: Dict[str, Any],
        existing_methodologies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Use LLM to determine whether the project fits an existing methodology."""
        system_prompt = (
            "You are a carbon credit methodology expert. Given a project description, "
            "determine whether it can use an existing approved methodology. Be conservative: "
            "if an existing methodology could apply, say so. Output strict JSON with keys: "
            "fits_existing_methodology (bool), matching_methodologies (list of objects with "
            "name, reason), gaps (list of strings explaining why existing methodologies do not fit), "
            "and recommendation (string advising next steps)."
        )
        user_prompt = f"""Project: {project_context.get('name')}
Sector: {project_context.get('sector')}
Activity: {project_context.get('activity_description')}
Boundaries: {json.dumps(project_context.get('boundaries', {}))}
Data sources: {json.dumps(project_context.get('data_sources', []))}
Existing methodologies: {json.dumps(existing_methodologies[:20])}"""

        response = await self.llm.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1536,
        )
        return self._parse_json_response(response.get("content", "{}"))

    async def generate_methodology(
        self,
        project_context: Dict[str, Any],
        gap_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a structured draft methodology and quantification scaffold."""
        system_prompt = (
            "You are drafting a carbon credit methodology aligned with Verra VCS and Gold Standard "
            "requirements. Output strict JSON with top-level keys: applicability_conditions, "
            "baseline_scenario, project_scenario, additionality_approach, quantification_approach, "
            "leakage_assessment, monitoring_plan, uncertainty_approach, safeguards, co_benefits, "
            "registry_alignment_notes. Each value should be a detailed paragraph or list. "
            "Additionally output a nested object quantification_scaffold with keys: equations "
            "(list of LaTeX-like strings), parameters (list of objects with name, description, unit, "
            "data_source, uncertainty), and monitoring_frequency (string)."
        )
        user_prompt = f"""Project: {project_context.get('name')}
Sector: {project_context.get('sector')}
Activity: {project_context.get('activity_description')}
Boundaries: {json.dumps(project_context.get('boundaries', {}))}
Data sources: {json.dumps(project_context.get('data_sources', []))}
Gap analysis: {json.dumps(gap_analysis)}"""

        response = await self.llm.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        parsed = self._parse_json_response(response.get("content", "{}"))
        return {
            "methodology": {k: v for k, v in parsed.items() if k != "quantification_scaffold"},
            "quantification_scaffold": parsed.get("quantification_scaffold", {}),
        }

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Extract JSON from an LLM response, tolerating markdown fences."""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```json", 1)[-1].split("```", 1)[0].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error(
                "methodology_generator_json_parse_failed",
                content=content[:200],
                error=str(exc),
            )
            return {"error": "Failed to parse AI response", "raw": content}
