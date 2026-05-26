"""CDM registry scraper.

CDM (Clean Development Mechanism) project search at cdm.unfccc.int uses
Incapsula bot protection. Playwright with non-headless mode is required
to bypass the challenge and submit the search form.
"""

import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

from app.services.lead_intelligence.base import BaseRegistryScraper
from app.core.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

DEMO_CDM_LEADS: List[Dict[str, Any]] = [
    {
        "external_id": "CDM-4321",
        "project_name": "Kenya Improved Biomass Cookstove",
        "project_developer": "Carbon Africa Ventures",
        "developer_contact": "+254 722 555666",
        "developer_email": "projects@carbonafrica.com",
        "country": "Kenya",
        "region": "Nairobi / Central",
        "methodology": "AMS-II.G",
        "sector": "Energy Efficiency",
        "status": "registered",
        "crediting_period_start": "2015-01-01",
        "crediting_period_end": "2024-12-31",
        "last_verification_date": "2019-06-30",
        "estimated_credits_per_year": 6000.0,
        "registry_url": "https://cdm.unfccc.int/Projects/DB/DNV-CUK1341997645.3/view",
        "days_in_status": 1825,
    },
    {
        "external_id": "CDM-4455",
        "project_name": "East African Biogas Programme",
        "project_developer": "Hivos Biogas Programme",
        "developer_contact": "+254 20 3870000",
        "developer_email": "biogas@hivos.org",
        "country": "Kenya",
        "region": "Multi-region",
        "methodology": "VM0050",
        "sector": "Agriculture/Forestry",
        "status": "registered",
        "crediting_period_start": "2012-01-01",
        "crediting_period_end": "2021-12-31",
        "last_verification_date": "2018-03-15",
        "estimated_credits_per_year": 25000.0,
        "registry_url": "https://cdm.unfccc.int/Projects/DB/SGS-UKL1258133759.36/view",
        "days_in_status": 2190,
    },
    {
        "external_id": "CDM-3987",
        "project_name": "Mombasa Landfill Gas Recovery",
        "project_developer": "Waste Energy Kenya",
        "developer_contact": "+254 722 445566",
        "developer_email": "info@wasteenergy.co.ke",
        "country": "Kenya",
        "region": "Mombasa",
        "methodology": "ACM0001",
        "sector": "Waste",
        "status": "registered",
        "crediting_period_start": "2015-01-01",
        "crediting_period_end": "2025-12-31",
        "last_verification_date": "2021-09-10",
        "estimated_credits_per_year": 55000.0,
        "registry_url": "https://cdm.unfccc.int/Projects/DB/TUEV-SUD1310527229.48/view",
        "days_in_status": 1100,
    },
]


def _parse_cdm_results(html: str) -> List[Dict[str, Any]]:
    """Parse CDM search result HTML and extract project data."""
    soup = BeautifulSoup(html, "html.parser")
    leads = []

    # Find the results table — look for rows after the header
    rows = soup.find_all("tr")
    in_results = False

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Detect header row
        if "Title" in texts and "Host Parties" in texts:
            in_results = True
            continue

        if not in_results:
            continue

        if len(texts) < 6:
            continue

        # CDM result row format:
        # [Registered date, Title, Host Parties, Other Parties, Methodology, Reductions, Ref]
        try:
            registered_date = texts[0]
            title = texts[1]
            host_parties = texts[2]
            other_parties = texts[3]
            methodology = texts[4]
            reductions = texts[5]
            ref = texts[6] if len(texts) > 6 else ""

            if not title or title == "Title":
                continue

            # Derive a project developer from host parties if available
            developer = host_parties if host_parties else "Unknown Developer"

            lead = {
                "external_id": f"CDM-{ref}" if ref else f"CDM-{hash(title) & 0xFFFFFF}",
                "project_name": title,
                "project_developer": developer,
                "developer_contact": None,
                "developer_email": None,
                "country": "Kenya" if "Kenya" in host_parties else host_parties.split(",")[0] if host_parties else None,
                "region": None,
                "methodology": methodology.split(" ver.")[0] if " ver." in methodology else methodology,
                "sector": None,
                "status": "registered",
                "crediting_period_start": None,
                "crediting_period_end": None,
                "last_verification_date": None,
                "estimated_credits_per_year": float(reductions.replace(",", "")) if reductions.replace(",", "").isdigit() else None,
                "registry_url": f"https://cdm.unfccc.int/Projects/DB/{ref}/view" if ref else None,
                "days_in_status": None,
            }
            leads.append(lead)
        except Exception as exc:
            logger.warning("cdm_parse_row_failed", texts=texts, error=str(exc))
            continue

    return leads


def _scrape_cdm_with_playwright(country: str) -> List[Dict[str, Any]]:
    """Use Playwright to submit the CDM search form and extract results.

    Incapsula blocks headless browsers, so we use headless=False.
    Uses the persistent browser singleton to avoid ~40s launch cost.
    """
    try:
        from playwright_stealth import Stealth
        from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser
    except ImportError:
        logger.warning("playwright_not_installed")
        return []

    logger.info("cdm_playwright_scrape_start", country=country)

    try:
        from app.services.lead_intelligence.playwright_utils import _new_stealth_page
        browser = _get_or_launch_browser(headless=False)
        page = _new_stealth_page(browser)

        page.goto(
            "https://cdm.unfccc.int/Projects/projsearch.html",
            timeout=30000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(2000)

        # Fill search form
        page.fill('input[name=titleFT]', country)
        page.click('input[name=button][value=Search]')
        page.wait_for_timeout(5000)

        html = page.content()
        final_url = page.url
        context.close()

        logger.info("cdm_playwright_page_fetched", url=final_url, html_length=len(html))

        leads = _parse_cdm_results(html)
        logger.info("cdm_playwright_parse_complete", count=len(leads))
        return leads

    except Exception as exc:
        logger.error("cdm_playwright_failed", error=str(exc))
        return []


class CDMScraper(BaseRegistryScraper):
    source = "cdm"

    def __init__(self):
        self.live_mode = settings.LEAD_SCRAPER_MODE == "live"

    def health_check(self) -> Dict[str, Any]:
        if not self.live_mode:
            return {"status": "demo", "message": "Demo mode active — set LEAD_SCRAPER_MODE=live to enable real scraping"}

        try:
            from playwright_stealth import Stealth
            from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser

            browser = _get_or_launch_browser(headless=False)
            page = _new_stealth_page(browser)
            page.goto(
                "https://cdm.unfccc.int/Projects/projsearch.html",
                timeout=30000,
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(3000)
            has_form = page.query_selector('form[name=searchform]') is not None
            context.close()

            if has_form:
                return {"status": "healthy", "message": "CDM registry reachable via Playwright"}
            return {"status": "blocked", "message": "CDM form not found"}
        except Exception as exc:
            return {"status": "error", "message": f"Playwright error: {str(exc)}"}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("cdm_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            live_leads = _scrape_cdm_with_playwright(country)
            if live_leads:
                for lead in live_leads:
                    lead["registry_source"] = self.source
                    lead["scraped_at"] = datetime.now(timezone.utc).isoformat()
                leads.extend(live_leads)
                data_source = "live"
            else:
                logger.warning("cdm_live_scrape_empty", country=country, falling_back="demo")

        if not leads:
            data_source = "demo"
            for raw in DEMO_CDM_LEADS:
                if country and raw.get("country") != country:
                    continue
                if status_filter != "all" and raw.get("status") != status_filter:
                    continue
                raw_copy = raw.copy()
                raw_copy["registry_source"] = self.source
                raw_copy["scraped_at"] = datetime.now(timezone.utc).isoformat()
                leads.append(raw_copy)

        logger.info("cdm_scrape_completed", count=len(leads), live_mode=self.live_mode, data_source=data_source)
        for lead in leads:
            lead["_scrape_meta"] = {"source": self.source, "data_source": data_source}
        return leads

    def close(self) -> None:
        pass
