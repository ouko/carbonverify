"""AI-driven custom methodology generation service."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.services.kimi_api import KimiAPIClient
from app.models import GeneratedMethodology, MethodologyVersion, MethodologyTemplate
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
        if not self.llm.api_key:
            logger.warning("methodology_generator_no_api_key", stage="analyze_gap")
            return self._placeholder_gap_analysis(project_context)

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
        if not self.llm.api_key:
            logger.warning("methodology_generator_no_api_key", stage="generate_methodology")
            return self._placeholder_methodology(project_context)

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

    def _placeholder_gap_analysis(self, project_context: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured placeholder gap analysis when no AI key is available."""
        name = project_context.get("name", "the project")
        sector = project_context.get("sector", "the selected sector")
        return {
            "fits_existing_methodology": False,
            "matching_methodologies": [],
            "gaps": [
                f"No approved methodology currently covers {name} in the {sector} sector.",
                "The project boundary and data sources differ from standard registry templates.",
                "A custom quantification approach is needed to capture the specific activity.",
            ],
            "recommendation": (
                "Configure KIMI_API_KEY to receive an AI-generated gap analysis. "
                "This placeholder allows you to test the workflow end-to-end."
            ),
        }

    def _placeholder_methodology(self, project_context: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured placeholder methodology when no AI key is available."""
        name = project_context.get("name", "the project")
        sector = project_context.get("sector", "the selected sector")
        boundaries = project_context.get("boundaries", {})
        data_sources = project_context.get("data_sources", [])
        return {
            "methodology": {
                "applicability_conditions": (
                    f"This methodology applies to {name} within the {sector} sector. "
                    "It is intended for activities that cannot be covered by an existing approved methodology."
                ),
                "baseline_scenario": (
                    "The baseline scenario describes the emissions that would occur in the absence of the project. "
                    "It should be conservative, transparent, and based on verifiable data sources."
                ),
                "project_scenario": (
                    "The project scenario describes the activity implemented by the project proponent, "
                    "including technology, scale, and operational parameters."
                ),
                "additionality_approach": (
                    "Demonstrate additionality using investment analysis, barrier analysis, or regulatory surplus, "
                    "as appropriate for the project type."
                ),
                "quantification_approach": (
                    "Emission reductions are quantified as the difference between baseline and project emissions, "
                    "minus leakage, using the equations in the quantification scaffold."
                ),
                "leakage_assessment": (
                    "Identify and quantify significant leakage sources, including activity-shifting, market, "
                    "and spatial leakage where relevant."
                ),
                "monitoring_plan": (
                    "Monitoring parameters are drawn from the data sources listed by the user and measured "
                    "at the frequency required to ensure conservativeness and accuracy."
                ),
                "uncertainty_approach": (
                    "Apply IPCC good-practice guidance for uncertainty assessment, propagating input uncertainties "
                    "through the quantification equations."
                ),
                "safeguards": (
                    "Describe environmental and social safeguards, stakeholder consultation, and grievance mechanisms."
                ),
                "co_benefits": (
                    "Document sustainable-development co-benefits, including health, livelihood, and biodiversity impacts."
                ),
                "registry_alignment_notes": (
                    "This placeholder draft follows the structure expected by Verra VCS and Gold Standard. "
                    "Configure KIMI_API_KEY to receive an AI-generated draft tailored to the project."
                ),
            },
            "quantification_scaffold": {
                "equations": ["ER_y = BE_y - PE_y - L_y"],
                "parameters": [
                    {
                        "name": "BE_y",
                        "description": "Baseline emissions in year y",
                        "unit": "tCO2e/yr",
                        "data_source": data_sources[0].get("source_type", "project data") if data_sources else "project data",
                        "uncertainty": "0.10",
                    },
                    {
                        "name": "PE_y",
                        "description": "Project emissions in year y",
                        "unit": "tCO2e/yr",
                        "data_source": data_sources[0].get("source_type", "project data") if data_sources else "project data",
                        "uncertainty": "0.08",
                    },
                    {
                        "name": "L_y",
                        "description": "Leakage emissions in year y",
                        "unit": "tCO2e/yr",
                        "data_source": "conservative estimate",
                        "uncertainty": "0.20",
                    },
                ],
                "monitoring_frequency": "annual",
                "project_boundary": boundaries.get("physical_boundary", "as described above"),
            },
        }


class MethodologyTemplateService:
    """Read-only helper for methodology starting templates."""

    async def list_active(
        self, db: AsyncSession
    ) -> List[MethodologyTemplate]:
        result = await db.execute(
            select(MethodologyTemplate).where(MethodologyTemplate.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get(
        self, db: AsyncSession, template_id: uuid.UUID
    ) -> Optional[MethodologyTemplate]:
        result = await db.execute(
            select(MethodologyTemplate).where(
                MethodologyTemplate.id == template_id,
                MethodologyTemplate.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    def defaults_to_form(self, template: MethodologyTemplate) -> Dict[str, Any]:
        """Return a safe, validated defaults dict for the frontend form."""
        raw = template.defaults_json or {}
        boundaries = raw.get("boundaries", {}) if isinstance(raw.get("boundaries"), dict) else {}
        data_sources = raw.get("data_sources", []) if isinstance(raw.get("data_sources"), list) else []
        return {
            "sector": template.sector,
            "boundaries": {
                "geographic_scope": str(boundaries.get("geographic_scope", "")),
                "temporal_scope": str(boundaries.get("temporal_scope", "")),
                "physical_boundary": str(boundaries.get("physical_boundary", "")),
                "ghg_sources_included": str(boundaries.get("ghg_sources_included", "")),
            },
            "data_sources": [
                {
                    "source_type": str(ds.get("source_type", "")) if isinstance(ds, dict) else "",
                    "description": str(ds.get("description", "")) if isinstance(ds, dict) else "",
                    "frequency": str(ds.get("frequency", "")) if isinstance(ds, dict) else "",
                    "provider_quality": str(ds.get("provider_quality", "")) if isinstance(ds, dict) else "",
                }
                for ds in data_sources
            ],
        }
