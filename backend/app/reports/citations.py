"""Citation management system for auto-linking numbers to sources."""

from typing import Dict, Any, List
from datetime import datetime

CITATION_LIBRARY = {
    "ipcc_2006_vol2_ch2": {
        "id": "C1",
        "text": "IPCC (2006). 2006 IPCC Guidelines for National Greenhouse Gas Inventories, Volume 2: Energy, Chapter 2: Stationary Combustion.",
        "url": "https://www.ipcc-nggip.iges.or.jp/public/2006gl/vol2.html",
    },
    "ipcc_ar6_gwp": {
        "id": "C2",
        "text": "IPCC (2021). Climate Change 2021: The Physical Science Basis. Contribution of Working Group I to the Sixth Assessment Report, Chapter 7.",
        "url": "https://www.ipcc.ch/report/ar6/wg1/",
    },
    "gs_tpddtec_v4": {
        "id": "C3",
        "text": "Gold Standard (2021). TPDDTEC v4: Technologies and Practices to Displace the Emission of Carbon from Traditional Cooking.",
        "url": "https://www.goldstandard.org/methodologies",
    },
    "verra_vm0050": {
        "id": "C4",
        "text": "Verra (2023). VM0050: Methodology for Metered and Measured Energy Cooking Devices, v1.2.",
        "url": "https://verra.org/methodology/vm0050/",
    },
    "verra_vcs_program": {
        "id": "C5",
        "text": "Verra (2023). VCS Standard v4.5.",
        "url": "https://verra.org/programs/verified-carbon-standard/",
    },
    "iso_19867": {
        "id": "C6",
        "text": "ISO (2018). ISO 19867-1:2018. Laboratory testing of cookstoves.",
        "url": "https://www.iso.org/standard/63619.html",
    },
    "gs_stove_database": {
        "id": "C7",
        "text": "Gold Standard (2023). Clean Cooking Stove Performance Database.",
        "url": "https://www.goldstandard.org/cookstove-database",
    },
    "who_guidelines_iaq": {
        "id": "C8",
        "text": "WHO (2014). WHO Guidelines for Indoor Air Quality: Household Fuel Combustion.",
        "url": "https://www.who.int/publications/i/item/9789241548878",
    },
    "mofuss_model": {
        "id": "C9",
        "text": "Masera et al. (2023). MoFuSS: Modeling Fuelwood Savings Scenarios.",
        "url": "https://mofuss.unam.mx/",
    },
}


def get_citations_for_calculation(methodology: str) -> List[Dict[str, str]]:
    """Return required citations for a given methodology."""
    citations = []
    
    # Always include IPCC
    citations.append(CITATION_LIBRARY["ipcc_2006_vol2_ch2"])
    citations.append(CITATION_LIBRARY["ipcc_ar6_gwp"])
    
    if methodology == "TPDDTEC_v4":
        citations.append(CITATION_LIBRARY["gs_tpddtec_v4"])
    elif methodology == "VM0050":
        citations.append(CITATION_LIBRARY["verra_vm0050"])
        citations.append(CITATION_LIBRARY["verra_vcs_program"])
    elif methodology == "VMR0006":
        citations.append(CITATION_LIBRARY["verra_vcs_program"])
    
    # Always include technical standards
    citations.append(CITATION_LIBRARY["iso_19867"])
    citations.append(CITATION_LIBRARY["gs_stove_database"])
    
    return citations


def auto_cite_number(value: float, context: str, methodology: str) -> Dict[str, Any]:
    """
    Auto-generate a citation for a numeric value based on context.
    
    Returns dict with value, citation_id, and source_text.
    """
    citation_map = {
        "emission_factor": "ipcc_2006_vol2_ch2",
        "gwp_value": "ipcc_ar6_gwp",
        "thermal_efficiency": "iso_19867",
        "fnrb": "mofuss_model",
        "baseline_stove_performance": "gs_stove_database",
        "health_impact": "who_guidelines_iaq",
    }
    
    cite_key = citation_map.get(context, "ipcc_2006_vol2_ch2")
    citation = CITATION_LIBRARY.get(cite_key, CITATION_LIBRARY["ipcc_2006_vol2_ch2"])
    
    return {
        "value": value,
        "citation_id": citation["id"],
        "source": citation["text"],
        "context": context,
    }


def build_citation_index(calculation_data: Dict[str, Any], methodology: str) -> List[Dict[str, str]]:
    """Build a complete citation index for a report."""
    citations = get_citations_for_calculation(methodology)
    
    # Add data source citations
    for ds in calculation_data.get("data_sources", []):
        cite_id = f"DS_{ds.get('id', 'unknown')[:8]}"
        citations.append({
            "id": cite_id,
            "text": f"Project Data Source: {ds.get('source_type', 'Unknown')} ({ds.get('schema_version', 'N/A')}), validation status: {ds.get('validation_status', 'Unknown')}.",
            "url": "",
        })
    
    return citations
