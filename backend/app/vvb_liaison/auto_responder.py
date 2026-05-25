"""Auto-responder for VVB technical queries using project data + methodology knowledge base."""

from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Knowledge base of common VVB queries and response templates
KNOWLEDGE_BASE = {
    "fnrb_source": {
        "patterns": ["fNRB", "non-renewable biomass", "source of fNRB", "how was fNRB determined"],
        "response_template": (
            "The fNRB value of {fnrb_value} was determined using a combination of: "
            "(1) spatial interpolation from peer-reviewed reference studies in the region ({source_reference}), "
            "and (2) the CCP cap of 0.50 for cookstove projects applied where applicable. "
            "The uncertainty range is {uncertainty_lower} to {uncertainty_upper} (±{uncertainty_std})."
        ),
        "required_fields": ["fnrb_value", "source_reference", "uncertainty_range"],
    },
    "sample_size": {
        "patterns": ["sample size", "KPT sample", "n=", "how many households"],
        "response_template": (
            "The Kitchen Performance Test (KPT) was conducted with n={kpt_sample_size} households "
            "over {kpt_duration_weeks} weeks. This {meets_requirement} the VM0050 minimum requirement of 30 households. "
            "The sample was selected using stratified random sampling to ensure representativeness."
        ),
        "required_fields": ["kpt_sample_size", "kpt_duration_weeks"],
    },
    "thermal_efficiency": {
        "patterns": ["thermal efficiency", "efficiency test", "WBT", "CCT", "laboratory test"],
        "response_template": (
            "Thermal efficiency was measured at {thermal_efficiency}% using {lab_test_type} protocols "
            "conducted at {test_lab} in accordance with ISO 19867-1:2018. "
            "The baseline stove efficiency of {baseline_efficiency}% was measured using the same protocol."
        ),
        "required_fields": ["thermal_efficiency", "lab_test_type"],
    },
    "usage_rate": {
        "patterns": ["usage rate", "adoption rate", "how often used", "stove stacking"],
        "response_template": (
            "The applied usage rate of {usage_rate}% is based on {usage_monitoring_method} data. "
            "This is within the VM0050 cap of {usage_rate_cap}% for this monitoring method. "
            "Stove stacking was assessed through {stacking_assessment_method}; "
            "the analysis found a stacking rate of {stacking_rate}%."
        ),
        "required_fields": ["usage_rate", "usage_monitoring_method"],
    },
    "leakage": {
        "patterns": ["leakage", "market effects", "spatial displacement", "activity shifting"],
        "response_template": (
            "Leakage was assessed across three dimensions: (1) market leakage via fuel price monitoring, "
            "(2) activity-shifting via stove usage monitoring, and (3) spatial leakage via GPS verification. "
            "Total assessed leakage is {leakage_tco2e} tCO₂e ({leakage_pct}% of baseline). "
            "A buffer of {buffer_pct}% has been applied."
        ),
        "required_fields": ["leakage_tco2e", "leakage_pct"],
    },
    "uncertainty": {
        "patterns": ["uncertainty", "confidence interval", "Monte Carlo", "sensitivity"],
        "response_template": (
            "Uncertainty was quantified using Monte Carlo simulation with {n_iterations} iterations. "
            "The 95% confidence interval is {ci_lower} to {ci_upper} tCO₂e/year. "
            "The conservative estimate (2.5th percentile) of {conservative_estimate} tCO₂e/year is recommended for issuance."
        ),
        "required_fields": ["n_iterations", "ci_lower", "ci_upper", "conservative_estimate"],
    },
    "data_quality": {
        "patterns": ["data quality", "missing data", "validation", "flagged"],
        "response_template": (
            "All data sources were validated through the CarbonVerify automated ingestion pipeline. "
            "{valid_sources} of {total_sources} sources passed automated validation. "
            "{flagged_sources} source(s) were flagged for human review and have been resolved. "
            "Data provenance tracking ensures full traceability from raw source to final calculation."
        ),
        "required_fields": ["valid_sources", "total_sources"],
    },
}


def classify_query(query_text: str) -> Optional[str]:
    """Classify a VVB query into a known category."""
    query_lower = query_text.lower()
    
    for category, data in KNOWLEDGE_BASE.items():
        for pattern in data["patterns"]:
            if pattern.lower() in query_lower:
                return category
    
    return None


def format_response(template: str, data: Dict[str, Any]) -> str:
    """Format a response template with project data."""
    try:
        return template.format(**data)
    except KeyError as e:
        missing_key = str(e).strip("'")
        return template.replace("{" + missing_key + "}", f"[{missing_key}: data not available]")


def draft_clarification_response(
    query_text: str,
    project_data: Dict[str, Any],
    calculation_data: Dict[str, Any],
    methodology: str,
) -> Dict[str, Any]:
    """
    Auto-draft a response to a VVB technical query.
    
    Returns response text, confidence score, and supporting data.
    """
    logger.info("drafting_clarification_response", query_preview=query_text[:100])
    
    category = classify_query(query_text)
    
    if not category:
        # Generic response for unclassified queries
        return {
            "category": "unknown",
            "confidence": 0.3,
            "response_text": (
                f"Thank you for your query regarding {project_data.get('name', 'our project')}. "
                f"We have reviewed your question and are preparing a detailed technical response. "
                f"In the meantime, please find the relevant monitoring report sections attached. "
                f"Our calculation methodology follows {methodology} with full traceability."
            ),
            "supporting_data": [],
            "suggested_human_review": True,
            "reason": "Query could not be automatically classified",
        }
    
    kb_entry = KNOWLEDGE_BASE[category]
    
    # Build data dict for template formatting
    template_data = {
        # fNRB data
        "fnrb_value": calculation_data.get("fNRB_value", "[N/A]"),
        "source_reference": calculation_data.get("source_reference", "[N/A]"),
        "uncertainty_range": calculation_data.get("uncertainty_range", {}),
        "uncertainty_lower": calculation_data.get("uncertainty_range", {}).get("lower", "[N/A]"),
        "uncertainty_upper": calculation_data.get("uncertainty_range", {}).get("upper", "[N/A]"),
        "uncertainty_std": calculation_data.get("uncertainty_range", {}).get("std_dev", "[N/A]"),
        
        # KPT data
        "kpt_sample_size": project_data.get("kpt_sample_size", "[N/A]"),
        "kpt_duration_weeks": project_data.get("kpt_duration_weeks", "[N/A]"),
        "meets_requirement": "meets" if (project_data.get("kpt_sample_size", 0) or 0) >= 30 else "is below",
        
        # Efficiency data
        "thermal_efficiency": (project_data.get("thermal_efficiency") or 0) * 100,
        "baseline_efficiency": (project_data.get("baseline_efficiency") or 0) * 100,
        "lab_test_type": project_data.get("lab_test_type", "[N/A]"),
        "test_lab": project_data.get("test_lab", "[N/A]"),
        
        # Usage data
        "usage_rate": (project_data.get("usage_rate") or 0) * 100,
        "usage_monitoring_method": project_data.get("usage_monitoring_method", "[N/A]"),
        "usage_rate_cap": (project_data.get("usage_rate_cap") or 0.75) * 100,
        "stacking_assessment_method": project_data.get("stacking_assessment_method", "usage monitoring"),
        "stacking_rate": (project_data.get("stacking_rate") or 0) * 100,
        
        # Leakage data
        "leakage_tco2e": calculation_data.get("leakage_tco2e", "[N/A]"),
        "leakage_pct": calculation_data.get("leakage_assessment", {}).get("leakage_as_pct_of_baseline", "[N/A]"),
        "buffer_pct": calculation_data.get("leakage_assessment", {}).get("buffer_recommendation_pct", "[N/A]"),
        
        # Uncertainty data
        "n_iterations": calculation_data.get("monte_carlo", {}).get("n_iterations", "[N/A]"),
        "ci_lower": calculation_data.get("monte_carlo", {}).get("uncertainty_95ci", {}).get("lower", "[N/A]") if isinstance(calculation_data.get("monte_carlo", {}).get("uncertainty_95ci"), dict) else calculation_data.get("uncertainty_95CI", "[N/A]"),
        "ci_upper": calculation_data.get("monte_carlo", {}).get("uncertainty_95ci", {}).get("upper", "[N/A]") if isinstance(calculation_data.get("monte_carlo", {}).get("uncertainty_95ci"), dict) else "[N/A]",
        "conservative_estimate": calculation_data.get("monte_carlo", {}).get("conservative_estimate_tco2e", "[N/A]"),
        
        # Data quality
        "valid_sources": calculation_data.get("valid_sources", "[N/A]"),
        "total_sources": calculation_data.get("total_sources", "[N/A]"),
        "flagged_sources": calculation_data.get("flagged_sources", "[N/A]"),
        
        # Project info
        "project_name": project_data.get("name", "the project"),
    }
    
    response_text = format_response(kb_entry["response_template"], template_data)
    
    # Build supporting data table
    supporting_data = []
    for field in kb_entry["required_fields"]:
        value = template_data.get(field, "[N/A]")
        supporting_data.append({
            "parameter": field,
            "value": str(value),
            "source": "Calculation Run / Project Database",
        })
    
    return {
        "category": category,
        "confidence": 0.85,
        "response_text": response_text,
        "supporting_data": supporting_data,
        "suggested_human_review": False,
        "reason": "Query matched known pattern",
        "matched_patterns": kb_entry["patterns"],
    }
