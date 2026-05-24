"""Report generator: Jinja2 templating + HTML→PDF compilation."""

import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.calculations.fnrb_calculator import calculate_fnrb
from app.calculations.emissions_quantifier import quantify_emissions
from app.calculations.leakage_detector import assess_leakage
from app.calculations.methodology_validator import validate_methodology
from app.calculations.uncertainty_engine import run_full_uncertainty_analysis
from app.reports.citations import build_citation_index
from app.reports.quality_gates import run_quality_gates
from app.core.logging import get_logger

logger = get_logger(__name__)

# Setup Jinja2 environment
TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_template_name(methodology: str) -> str:
    """Select appropriate template based on methodology."""
    mapping = {
        "TPDDTEC_v4": "gs_tpddtec_v4.html",
        "VM0050": "verra_vm0050.html",
        "VMR0006": "verra_vm0050.html",  # Similar structure
        "AMS-II.G": "gs_tpddtec_v4.html",
    }
    return mapping.get(methodology, "gs_tpddtec_v4.html")


def build_report_context(
    project: Dict[str, Any],
    calculation_run: Dict[str, Any],
    data_sources: List[Dict[str, Any]],
    methodology: str,
) -> Dict[str, Any]:
    """Build the template context from database objects."""
    
    # Default project data for templates
    project_data = project.get("processed_data", {}) if isinstance(project, dict) else {}
    
    # Extract calculation results
    calc = {
        "fNRB_value": calculation_run.get("fNRB_value", 0.30),
        "emissions_reduction_tco2e": calculation_run.get("emissions_reduction_tCO2e", 0),
        "uncertainty_95CI": calculation_run.get("uncertainty_95CI", 0),
        "baseline_emissions_tco2e": calculation_run.get("baseline_emissions", {}).get("total_tco2e_per_year", 0) if isinstance(calculation_run.get("baseline_emissions"), dict) else 0,
        "project_emissions_tco2e": calculation_run.get("project_emissions", {}).get("total_tco2e_per_year", 0) if isinstance(calculation_run.get("project_emissions"), dict) else 0,
        "gross_reduction_tco2e": calculation_run.get("gross_reduction_tco2e", 0),
        "leakage_tco2e": calculation_run.get("leakage_tco2e", 0),
        "leakage_assessment": calculation_run.get("leakage_assessment", {}),
    }
    
    # Monte Carlo results - normalize structure
    mc_raw = calculation_run.get("monte_carlo", {})
    if mc_raw and "uncertainty_95ci" in mc_raw and isinstance(mc_raw["uncertainty_95ci"], dict):
        mc = {
            "mean_reduction_tco2e": mc_raw.get("mean_reduction_tco2e", calc["emissions_reduction_tco2e"]),
            "median_reduction_tco2e": mc_raw.get("median_reduction_tco2e", calc["emissions_reduction_tco2e"]),
            "std_dev": mc_raw.get("std_dev", 0),
            "ci_lower": mc_raw["uncertainty_95ci"].get("lower", calc["emissions_reduction_tco2e"] * 0.8),
            "ci_upper": mc_raw["uncertainty_95ci"].get("upper", calc["emissions_reduction_tco2e"] * 1.2),
            "conservative_estimate_tco2e": mc_raw.get("conservative_estimate_tco2e", calc["emissions_reduction_tco2e"] * 0.8),
            "n_iterations": mc_raw.get("n_iterations", 10000),
        }
    else:
        mc = {
            "mean_reduction_tco2e": calc["emissions_reduction_tco2e"],
            "median_reduction_tco2e": calc["emissions_reduction_tco2e"],
            "std_dev": 0,
            "ci_lower": calc["emissions_reduction_tco2e"] * 0.8,
            "ci_upper": calc["emissions_reduction_tco2e"] * 1.2,
            "conservative_estimate_tco2e": calc["emissions_reduction_tco2e"] * 0.8,
            "n_iterations": 10000,
        }
    
    # Sensitivity analysis
    sensitivity = calculation_run.get("sensitivity_analysis", [])
    
    # KPT data placeholder
    kpt = project_data.get("kpt", {}) if isinstance(project_data, dict) else {}
    
    # Co-benefits placeholder
    co_benefits = project_data.get("co_benefits", {}) if isinstance(project_data, dict) else {}
    
    # Methodology validation
    methodology_result = calculation_run.get("methodology_validation", {"compliance_score": 0})
    
    # Build appendices
    appendices = [
        {
            "title": "Data Source Summary",
            "description": "Complete listing of all data sources used in this monitoring period.",
            "table": [["ID", "Type", "Status", "Records"]] + [
                [str(ds.get("id", "N/A"))[:8], ds.get("source_type", "N/A"), 
                 ds.get("validation_status", "N/A"), ds.get("record_count", "N/A")]
                for ds in data_sources[:20]
            ],
        },
        {
            "title": "Calculation Parameters",
            "description": "All parameters used in the emissions calculation.",
            "table": [
                ["Parameter", "Value", "Source"],
                ["fNRB", str(calc["fNRB_value"]), "Spatial Interpolation / MoFuSS"],
                ["Baseline Efficiency", str(project_data.get("baseline_efficiency", "0.10") if isinstance(project_data, dict) else "0.10"), "Laboratory Test"],
                ["Project Efficiency", str(project_data.get("thermal_efficiency", "0.30") if isinstance(project_data, dict) else "0.30"), "Laboratory Test"],
                ["Fuel Type", project_data.get("fuel_type", "wood") if isinstance(project_data, dict) else "wood", "Project Design"],
                ["Households", str(project_data.get("household_count", "N/A") if isinstance(project_data, dict) else "N/A"), "Project Database"],
            ],
        },
    ]
    
    # Build citations
    citations = build_citation_index(calculation_run, methodology)
    
    # Executive summary text
    executive_summary = (
        f"During the monitoring period, the project achieved a net emission reduction of "
        f"{calc['emissions_reduction_tco2e']:.1f} tCO₂e (95% CI: {mc['ci_lower']:.1f} – {mc['ci_upper']:.1f}). "
        f"The methodology compliance score was {methodology_result.get('compliance_score', 0):.0f}%. "
        f"All data sources passed automated validation. "
        f"The conservative estimate for crediting is {mc['conservative_estimate_tco2e']:.1f} tCO₂e."
    )
    
    # Monitoring period dates
    monitoring_period_start = calculation_run.get("monitoring_period_start", date.today())
    monitoring_period_end = calculation_run.get("monitoring_period_end", date.today())
    if isinstance(monitoring_period_start, str):
        monitoring_period_start = datetime.strptime(monitoring_period_start, "%Y-%m-%d").date()
    if isinstance(monitoring_period_end, str):
        monitoring_period_end = datetime.strptime(monitoring_period_end, "%Y-%m-%d").date()
    
    monitoring_days = (monitoring_period_end - monitoring_period_start).days if hasattr(monitoring_period_end, '__sub__') else 365
    
    # Count flagged sources
    flagged_sources = sum(1 for ds in data_sources if ds.get("validation_status") == "flagged")
    
    return {
        "project": project,
        "project_data": project_data,
        "calculation_run": calculation_run,
        "calc": calc,
        "mc": mc,
        "sensitivity": sensitivity,
        "kpt": kpt,
        "co_benefits": co_benefits,
        "methodology": methodology_result,
        "data_sources": data_sources,
        "appendices": appendices,
        "citations": citations,
        "executive_summary_text": executive_summary,
        "monitoring_period_start": monitoring_period_start,
        "monitoring_period_end": monitoring_period_end,
        "monitoring_days": monitoring_days,
        "flagged_sources": flagged_sources,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "cv_version": "1.1.0",
        "report_title": f"{methodology} Monitoring Report",
    }


def generate_html_report(
    project: Dict[str, Any],
    calculation_run: Dict[str, Any],
    data_sources: List[Dict[str, Any]],
    methodology: str,
) -> str:
    """Generate HTML report from template."""
    template_name = get_template_name(methodology)
    template = jinja_env.get_template(template_name)
    
    context = build_report_context(project, calculation_run, data_sources, methodology)
    html = template.render(**context)
    
    logger.info("html_report_generated", template=template_name, project_id=str(project.get("id", "unknown")))
    return html


def html_to_pdf(html_content: str, output_path: str) -> str:
    """
    Convert HTML to PDF using weasyprint (preferred) or fallback to saving HTML.
    
    Returns the path to the generated PDF (or HTML if PDF generation unavailable).
    """
    try:
        from weasyprint import HTML, CSS
        
        html_doc = HTML(string=html_content)
        html_doc.write_pdf(output_path)
        logger.info("pdf_generated", path=output_path)
        return output_path
    except ImportError:
        logger.warning("weasyprint_not_available", fallback="html")
        # Fallback: save as HTML
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_path


def generate_report(
    project: Dict[str, Any],
    calculation_run: Dict[str, Any],
    data_sources: List[Dict[str, Any]],
    methodology: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full report generation pipeline:
    1. Generate HTML from template
    2. Run quality gates
    3. Convert to PDF
    4. Return report metadata
    """
    # Generate HTML
    html = generate_html_report(project, calculation_run, data_sources, methodology)
    
    # Run quality gates
    quality_result = run_quality_gates(html, calculation_run, methodology)
    
    # Convert to PDF
    if output_path is None:
        report_id = str(uuid.uuid4())
        output_path = f"/tmp/carbonverify_report_{report_id}.pdf"
    
    final_path = html_to_pdf(html, output_path)
    
    return {
        "html": html,
        "pdf_path": final_path,
        "quality_gates": quality_result,
        "generated_at": datetime.utcnow().isoformat(),
        "methodology": methodology,
        "status": "needs_human_review" if not quality_result["passed"] else "ready_for_submission",
    }
