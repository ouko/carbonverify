"""Base scraper interface for carbon registry lead intelligence."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseRegistryScraper(ABC):
    """Abstract base class for registry scrapers.

    Subclasses must implement ``scrape()`` which returns a list of
    raw lead dicts. Each dict should contain the fields expected by
    ``LeadCreate`` (project_name, external_id, status, etc.).
    """

    source: str = ""

    @abstractmethod
    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        """Scrape the registry and return raw lead data.

        Args:
            country: Country filter (e.g. "Kenya", "Uganda").
            status_filter: Registry-specific status filter or "all".

        Returns:
            List of lead dicts ready for ingestion.
        """
        ...

    def fetch_documents(self, lead: "Lead") -> List[Dict[str, Any]]:
        """Return document metadata discovered on the registry page for this lead.

        Each dict must contain at least:
        - document_type: str (e.g. "pdd", "monitoring_report", "verification_report")
        - source_url: str
        - title: Optional[str]

        Subclasses should override this method.
        """
        return []

    def close(self) -> None:
        """Clean up any resources (HTTP clients, browsers, etc.)."""
        pass
