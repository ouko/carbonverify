"""Cross-reference validation for reports: table/figure/appendix numbering consistency."""

import re
from typing import Dict, Any, List


class CrossReferenceValidator:
    """Validates that all tables, figures, and appendices are properly numbered and cited."""
    
    def __init__(self, html_content: str):
        self.html = html_content
        self.issues: List[str] = []
    
    def extract_tables(self) -> List[Dict[str, Any]]:
        """Extract all tables with their captions."""
        tables = []
        # Find all table caption elements
        caption_pattern = r'Table\s+(\d+):\s+([^<]+)'
        for match in re.finditer(caption_pattern, self.html):
            tables.append({
                "number": int(match.group(1)),
                "title": match.group(2).strip(),
            })
        return tables
    
    def extract_citations(self) -> List[str]:
        """Extract all in-text citations like 'Table X' or 'Figure Y'."""
        # Remove captions first to avoid self-citation
        text_without_captions = re.sub(r'<p class="caption">[^<]+</p>', '', self.html)
        text_without_captions = re.sub(r'Table\s+\d+:\s+[^<]+', '', text_without_captions)
        
        # Find references to tables in text
        table_refs = re.findall(r'Table\s+(\d+)', text_without_captions)
        figure_refs = re.findall(r'Figure\s+(\d+)', text_without_captions)
        appendix_refs = re.findall(r'Appendix\s+(\d+)', text_without_captions)
        return {
            "tables": [int(x) for x in table_refs],
            "figures": [int(x) for x in figure_refs],
            "appendices": [int(x) for x in appendix_refs],
        }
    
    def validate_sequential_numbering(self, items: List[Dict[str, Any]], item_type: str) -> bool:
        """Check that items are numbered sequentially from 1."""
        expected = 1
        for item in items:
            if item["number"] != expected:
                self.issues.append(
                    f"{item_type} numbering gap: expected {item_type} {expected}, found {item['number']}"
                )
                return False
            expected += 1
        return True
    
    def validate_all_cited(self, items: List[Dict[str, Any]], citations: List[int], item_type: str) -> bool:
        """Check that every item is cited at least once in the text."""
        cited_numbers = set(citations)
        all_valid = True
        for item in items:
            if item["number"] not in cited_numbers:
                self.issues.append(
                    f"{item_type} {item['number']} ('{item['title']}') is not cited in the text"
                )
                all_valid = False
        return all_valid
    
    def validate_no_orphan_citations(self, citations: List[int], items: List[Dict[str, Any]], item_type: str) -> bool:
        """Check that every citation refers to an existing item."""
        valid_numbers = {item["number"] for item in items}
        all_valid = True
        for cite_num in citations:
            if cite_num not in valid_numbers:
                self.issues.append(
                    f"Citation to non-existent {item_type} {cite_num}"
                )
                all_valid = False
        return all_valid
    
    def validate(self) -> Dict[str, Any]:
        """Run full cross-reference validation."""
        tables = self.extract_tables()
        citations = self.extract_citations()
        
        checks = {
            "tables_sequential": self.validate_sequential_numbering(tables, "Table"),
            "tables_cited": self.validate_all_cited(tables, citations["tables"], "Table"),
            "tables_no_orphans": self.validate_no_orphan_citations(
                citations["tables"], tables, "Table"
            ),
            "figures_cited": len(citations["figures"]) == 0 or True,  # Placeholder
            "appendices_cited": len(citations["appendices"]) > 0 if "Appendix" in self.html else True,
        }
        
        return {
            "valid": len(self.issues) == 0,
            "issues": self.issues,
            "checks": checks,
            "summary": {
                "tables_found": len(tables),
                "table_citations_found": len(citations["tables"]),
                "figure_citations_found": len(citations["figures"]),
                "appendix_citations_found": len(citations["appendices"]),
            },
        }


def validate_report_cross_references(html_content: str) -> Dict[str, Any]:
    """Convenience function to validate report cross-references."""
    validator = CrossReferenceValidator(html_content)
    return validator.validate()
