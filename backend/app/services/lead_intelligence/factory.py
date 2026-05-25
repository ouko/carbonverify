"""Factory for registry scrapers."""

from typing import Dict, Type, Any

from app.services.lead_intelligence.base import BaseRegistryScraper
from app.services.lead_intelligence.verra import VerraScraper
from app.services.lead_intelligence.gold_standard import GoldStandardScraper
from app.services.lead_intelligence.cdm import CDMScraper
from app.config import get_settings

_SCRAPER_REGISTRY: Dict[str, Type[BaseRegistryScraper]] = {
    "verra": VerraScraper,
    "gold_standard": GoldStandardScraper,
    "cdm": CDMScraper,
}


def get_scraper(source: str) -> BaseRegistryScraper:
    """Return an instantiated scraper for the given registry source.

    Raises:
        ValueError: If the source is not supported.
    """
    scraper_cls = _SCRAPER_REGISTRY.get(source)
    if not scraper_cls:
        raise ValueError(f"Unknown registry source: {source}. Supported: {list(_SCRAPER_REGISTRY.keys())}")
    return scraper_cls()


def list_scrapers() -> list[str]:
    """Return list of supported registry source names."""
    return list(_SCRAPER_REGISTRY.keys())


def health_check_all() -> Dict[str, Any]:
    """Run health checks on all scrapers and return status."""
    settings = get_settings()
    results = {}
    for name, scraper_cls in _SCRAPER_REGISTRY.items():
        scraper = scraper_cls()
        try:
            results[name] = scraper.health_check()
        except Exception as exc:
            results[name] = {"status": "error", "message": str(exc)}
        finally:
            scraper.close()
    results["mode"] = settings.LEAD_SCRAPER_MODE
    return results
