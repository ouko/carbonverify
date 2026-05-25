"""CDM (UNFCCC) registry scraper.

CDM URL: https://cdm.unfccc.int/Projects/projsearch.html
The CDM registry uses older ASP.NET web forms. It requires POST requests
with viewstate/__EVENTVALIDATION tokens, making simple scraping difficult.

To enable live scraping, either:
  1. Use Playwright/Selenium to drive the form submission
  2. Parse the HTML response with BeautifulSoup after form submission
  3. Use the CDM project database XML export if available

Set LEAD_SCRAPER_MODE=live in your .env to attempt live scraping.
"""

import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

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
        "project_name": "Kenya Off-Grid Solar",
        "project_developer": "SunFunder Carbon",
        "developer_contact": None,
        "developer_email": "carbon@sunfunder.com",
        "country": "Kenya",
        "region": "Nationwide",
        "methodology": "VMR0006",
        "sector": "Energy",
        "status": "registered",
        "crediting_period_start": "2014-01-01",
        "crediting_period_end": "2023-12-31",
        "last_verification_date": "2017-11-20",
        "estimated_credits_per_year": 12000.0,
        "registry_url": "https://cdm.unfccc.int/Projects/DB/TUV-SUD1448555963.98/view",
        "days_in_status": 2555,
    },
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class CDMScraper(BaseRegistryScraper):
    source = "cdm"

    def __init__(self):
        self.client: Optional[httpx.Client] = None
        self.live_mode = settings.LEAD_SCRAPER_MODE == "live"
        self.rate_limit_delay = 1.0 / settings.LEAD_SCRAPER_RATE_LIMIT_RPS

    def _get_client(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(
                headers=DEFAULT_HEADERS,
                timeout=settings.LEAD_SCRAPER_REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self.client

    def _try_live_scrape(self, country: str, status_filter: str) -> List[Dict[str, Any]]:
        logger.info("cdm_live_scrape_attempt", country=country)
        # CDM uses ASP.NET web forms with __VIEWSTATE and __EVENTVALIDATION.
        # A full implementation would:
        #   1. GET the search page to extract the form tokens
        #   2. POST with country filter and tokens
        #   3. Parse the paginated results
        #   4. Visit each project detail page
        # This requires Playwright or careful form handling.
        url = "https://cdm.unfccc.int/Projects/projsearch.html"
        client = self._get_client()
        try:
            time.sleep(self.rate_limit_delay)
            resp = client.get(url, timeout=10)
            if resp.status_code == 200 and "Project Search" in resp.text:
                logger.info("cdm_search_page_reachable")
                # TODO: Implement form token extraction + submission + result parsing
            else:
                logger.warning("cdm_search_page_blocked", status=resp.status_code)
        except Exception as exc:
            logger.warning("cdm_fetch_error", error=str(exc))

        logger.warning("cdm_live_scrape_not_yet_implemented", country=country)
        return []

    def health_check(self) -> Dict[str, Any]:
        if not self.live_mode:
            return {"status": "demo", "message": "Demo mode active — set LEAD_SCRAPER_MODE=live to enable real scraping"}
        url = "https://cdm.unfccc.int/Projects/projsearch.html"
        client = self._get_client()
        try:
            resp = client.get(url, timeout=10)
            if resp.status_code == 200 and "Project Search" in resp.text:
                return {"status": "healthy", "message": "CDM registry reachable"}
            return {"status": "blocked", "message": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("cdm_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            live_leads = self._try_live_scrape(country, status_filter)
            if live_leads:
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
        if self.client:
            self.client.close()
            self.client = None
