"""Tests for registry scrapers in demo mode."""

import pytest

from app.services.lead_intelligence.verra import VerraScraper
from app.services.lead_intelligence.gold_standard import GoldStandardScraper
from app.services.lead_intelligence.cdm import CDMScraper
from app.services.lead_intelligence.factory import get_scraper, list_scrapers


@pytest.fixture(autouse=True)
def force_demo_mode(monkeypatch):
    """Force demo mode on all scrapers to avoid network calls."""

    def _patch_init(cls):
        orig = cls.__init__

        def patched(self, *args, **kwargs):
            orig(self, *args, **kwargs)
            self.live_mode = False

        monkeypatch.setattr(cls, "__init__", patched)

    _patch_init(GoldStandardScraper)
    _patch_init(CDMScraper)
    _patch_init(VerraScraper)


class TestVerraScraper:
    def test_scrape_returns_leads(self):
        scraper = VerraScraper()
        leads = scraper.scrape(country="Kenya")
        assert len(leads) > 0
        assert all(l["registry_source"] == "verra" for l in leads)
        assert all("project_name" in l for l in leads)

    def test_scrape_filter_by_country(self):
        scraper = VerraScraper()
        leads = scraper.scrape(country="Uganda")
        assert len(leads) == 0  # Demo data is Kenya-only


class TestGoldStandardScraper:
    def test_scrape_returns_leads(self):
        scraper = GoldStandardScraper()
        leads = scraper.scrape(country="Kenya")
        assert len(leads) > 0
        assert all(l["registry_source"] == "gold_standard" for l in leads)


class TestCDMScraper:
    def test_scrape_returns_leads(self):
        scraper = CDMScraper()
        leads = scraper.scrape(country="Kenya")
        assert len(leads) > 0
        assert all(l["registry_source"] == "cdm" for l in leads)


class TestFactory:
    def test_list_scrapers(self):
        scrapers = list_scrapers()
        assert "verra" in scrapers
        assert "gold_standard" in scrapers
        assert "cdm" in scrapers

    def test_get_scraper(self):
        for name in list_scrapers():
            scraper = get_scraper(name)
            assert scraper.source == name

    def test_get_scraper_unknown(self):
        with pytest.raises(ValueError):
            get_scraper("nonexistent")
