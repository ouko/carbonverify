"""Quality Gates: automated checks + human review queue integration."""

import re
from typing import Dict, Any, List

from app.reports.cross_references import validate_report_cross_references
from app.core.logging import get_logger

logger = get_logger(__name__)


class AutomatedQualityGate:
    """Runs automated quality checks on generated report HTML/content."""
    
    def __init__(self, html_content: str, calculation_data: Dict[str, Any]):
        self.html = html_content
        self.calc = calculation_data
        self.issues: List[str] = []
        self.warnings: List[str] = []
    
    def check_methodology_completeness(self, methodology: str) -> bool:
        """Check that required methodology sections are present."""
        required_sections = {
            "TPDDTEC_v4": [
                "Executive Summary",
                "Project Description",
                "Monitoring Period",
                "Stove Distribution",
                "Kitchen Performance Test",
                "Thermal Efficiency",
                "Emissions Reduction",
                "Leakage",
                "Uncertainty",
            ],
            "VM0050": [
                "Executive Summary",
                "Baseline Scenario",
                "Project Scenario",
                "Monitoring Data",
                "Emission Reductions",
                "Leakage",
                "Uncertainty",
            ],
        }
        
        sections = required_sections.get(methodology, [])
        missing = []
        for section in sections:
            # Check for section heading or partial match
            section_lower = section.lower()
            html_lower = self.html.lower()
            if section_lower not in html_lower:
                # Try partial match for multi-word sections
                words = section_lower.split()
                if not any(word in html_lower for word in words if len(word) > 4):
                    missing.append(section)
        
        if missing:
            self.issues.append(f"Missing required sections for {methodology}: {', '.join(missing)}")
            return False
        return True
    
    def check_citation_completeness(self) -> bool:
        """Check that all numbers have associated citations."""
        # Simple heuristic: check for citation markers near numbers
        # Look for patterns like "123.4 tCO2e" without a nearby citation
        number_pattern = r'\d+\.?\d*\s*(?:tCO2e|kg|kg/day|%|percent)'
        numbers = re.findall(number_pattern, self.html)
        
        uncited_count = 0
        for num in numbers[:50]:  # Check first 50 numbers
            # Find position of number
            pos = self.html.find(num)
            surrounding = self.html[max(0, pos-200):pos+200]
            if '[C' not in surrounding and 'Table' not in surrounding:
                uncited_count += 1
        
        if uncited_count > 10:
            self.warnings.append(f"{uncited_count} numeric values may lack proper citations")
            return False
        return True
    
    def check_calculation_consistency(self) -> bool:
        """Verify that reported numbers match calculation data."""
        issues_found = False
        
        # Check emissions reduction value
        if self.calc.get("emissions_reduction_tco2e"):
            expected = f"{self.calc['emissions_reduction_tco2e']:.1f}"
            if expected not in self.html:
                self.issues.append(
                    f"Reported emissions reduction ({expected}) not found in report text"
                )
                issues_found = True
        
        # Check fNRB value
        if self.calc.get("fNRB_value"):
            expected_fnrb = str(self.calc["fNRB_value"])
            if expected_fnrb not in self.html:
                self.issues.append(f"fNRB value ({expected_fnrb}) not found in report text")
                issues_found = True
        
        return not issues_found
    
    def check_grammar_style(self) -> bool:
        """Basic grammar/style checks (placeholder for language-tool integration)."""
        # Common issues
        issues = []
        
        # Double spaces
        if "  " in self.html:
            issues.append("Double spaces detected")
        
        # Empty paragraphs
        if "<p></p>" in self.html or "<p> </p>" in self.html:
            issues.append("Empty paragraphs detected")
        
        # Very long sentences (>40 words)
        text_only = re.sub(r'<[^>]+>', ' ', self.html)
        sentences = re.split(r'[.!?]+', text_only)
        long_sentences = [s.strip() for s in sentences if len(s.split()) > 40]
        if len(long_sentences) > 5:
            issues.append(f"{len(long_sentences)} sentences exceed 40 words")
        
        if issues:
            self.warnings.extend(issues)
            return False
        return True
    
    def run_all_checks(self, methodology: str) -> Dict[str, Any]:
        """Run all automated quality gates."""
        logger.info("running_quality_gates", methodology=methodology)
        
        # Cross-reference validation
        xref_result = validate_report_cross_references(self.html)
        if not xref_result["valid"]:
            self.issues.extend(xref_result["issues"])
        
        # Methodology completeness
        self.check_methodology_completeness(methodology)
        
        # Citation completeness
        self.check_citation_completeness()
        
        # Calculation consistency
        self.check_calculation_consistency()
        
        # Grammar/style
        self.check_grammar_style()
        
        return {
            "passed": len(self.issues) == 0,
            "issues": self.issues,
            "warnings": self.warnings,
            "cross_reference_validation": xref_result,
            "severity": "critical" if self.issues else ("warning" if self.warnings else "pass"),
        }


def run_quality_gates(
    html_content: str,
    calculation_data: Dict[str, Any],
    methodology: str,
) -> Dict[str, Any]:
    """Run full automated quality gate suite."""
    gate = AutomatedQualityGate(html_content, calculation_data)
    result = gate.run_all_checks(methodology)
    
    logger.info(
        "quality_gates_complete",
        passed=result["passed"],
        issue_count=len(result["issues"]),
        warning_count=len(result["warnings"]),
    )
    
    return result
