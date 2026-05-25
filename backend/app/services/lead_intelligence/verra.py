"""Verra registry scraper.

Verra Registry uses a JavaScript-heavy frontend with Cloudflare protection.
Direct API access is limited. This scraper attempts live HTTP calls and
falls back to demo data when blocked.

Known endpoints:
  - Search UI: https://registry.verra.org/app/search/VCS/All%20Projects
  - Project detail (guest): https://registry.verra.org/ui/guest/projectSummary/VCS/VCU/{id}
  - The registry does NOT expose a public REST API for unauthenticated bulk queries.

To enable full live scraping, install Playwright:
    uv pip install playwright
    playwright install chromium

Then set LEAD_SCRAPER_MODE=live in your .env file.
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

# Demo data for Kenya projects
DEMO_VERRA_LEADS: List[Dict[str, Any]] = [
    {
        "external_id": "VCS-VCU-1952",
        "project_name": "Kenya Household Energy Project — Embu",
        "project_developer": "EcoAct Kenya Ltd",
        "developer_contact": "+254 722 123456",
        "developer_email": "projects@ecoact.co.ke",
        "country": "Kenya",
        "region": "Embu County",
        "methodology": "VMR0006",
        "sector": "Energy",
        "status": "under_verification",
        "crediting_period_start": "2022-01-01",
        "crediting_period_end": "2031-12-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 45000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/1952",
        "days_in_status": 245,
    },
    {
        "external_id": "VCS-VCU-2087",
        "project_name": "Borehole Rehabilitation Programme — Kwale",
        "project_developer": "CarbonLink Africa",
        "developer_contact": None,
        "developer_email": "info@carbonlink.africa",
        "country": "Kenya",
        "region": "Kwale County",
        "methodology": "VM0050",
        "sector": "Energy Efficiency",
        "status": "under_validation",
        "crediting_period_start": "2021-06-01",
        "crediting_period_end": "2028-05-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 12000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/2087",
        "days_in_status": 420,
    },
    {
        "external_id": "VCS-VCU-1543",
        "project_name": "Lake Turkana Wind Power",
        "project_developer": "LTWP Kenya",
        "developer_contact": "+254 20 1234567",
        "developer_email": "carbon@ltwp.co.ke",
        "country": "Kenya",
        "region": "Marsabit County",
        "methodology": "VM0055",
        "sector": "Energy",
        "status": "registered",
        "crediting_period_start": "2019-01-01",
        "crediting_period_end": "2038-12-31",
        "last_verification_date": "2022-03-15",
        "estimated_credits_per_year": 320000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/1543",
        "days_in_status": 890,
    },
    {
        "external_id": "VCS-VCU-2311",
        "project_name": "Nairobi Improved Cookstoves Distribution",
        "project_developer": "GreenChar Kenya",
        "developer_contact": "+254 733 987654",
        "developer_email": "mrv@greenchar.org",
        "country": "Kenya",
        "region": "Nairobi",
        "methodology": "AMS-II.G",
        "sector": "Energy Efficiency",
        "status": "under_verification",
        "crediting_period_start": "2023-01-01",
        "crediting_period_end": "2032-12-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 8500.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/2311",
        "days_in_status": 95,
    },
    {
        "external_id": "VCS-VCU-1899",
        "project_name": "Western Kenya Cookstove Project",
        "project_developer": "EcoDev Ltd",
        "developer_contact": "+254 722 111222",
        "developer_email": "carbon@ecodev.co.ke",
        "country": "Kenya",
        "region": "Kakamega",
        "methodology": "TPDDTEC_v4",
        "sector": "Household Devices",
        "status": "registered",
        "crediting_period_start": "2020-01-01",
        "crediting_period_end": "2029-12-31",
        "last_verification_date": "2021-08-20",
        "estimated_credits_per_year": 18000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/1899",
        "days_in_status": 1050,
    },
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}


class VerraScraper(BaseRegistryScraper):
    source = "verra"

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
                http2=True,
            )
        return self.client

    def _fetch_project_page(self, project_id: str) -> Optional[str]:
        """Fetch raw HTML for a single Verra project page."""
        url = f"https://registry.verra.org/app/projectDetail/VCS/VCU/{project_id}"
        client = self._get_client()
        for attempt in range(settings.LEAD_SCRAPER_MAX_RETRIES):
            try:
                time.sleep(self.rate_limit_delay)
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.text
                logger.warning("verra_fetch_failed", project_id=project_id, status=resp.status_code)
            except Exception as exc:
                logger.warning("verra_fetch_error", project_id=project_id, attempt=attempt, error=str(exc))
                time.sleep(settings.LEAD_SCRAPER_RETRY_DELAY)
        return None

    def _try_live_scrape(self, country: str, status_filter: str) -> List[Dict[str, Any]]:
        """Attempt to scrape Verra live. Returns empty list if blocked."""
        logger.info("verra_live_scrape_attempt", country=country)

        # Verra's search page is JS-driven; without Playwright we can't execute the search.
        # As a fallback, we attempt to fetch known Kenya project IDs from the registry.
        # In production, this should be replaced with a Playwright-based crawler that:
        #   1. Opens https://registry.verra.org/app/search/VCS/All%20Projects
        #   2. Fills country=Kenya, clicks Search
        #   3. Parses the paginated results table
        #   4. Visits each project detail page for full data

        known_ids = ["1525", "1543", "1899", "1952", "2087", "2311"]
        leads = []
        for vid in known_ids:
            html = self._fetch_project_page(vid)
            if html is None:
                continue
            # Basic HTML parsing would go here with BeautifulSoup
            # For now, we detect if we got a real page vs a block page
            if "Project Details" in html or "Project Name" in html or "crediting period" in html.lower():
                logger.info("verra_page_fetched", project_id=vid)
                # TODO: Parse HTML with BeautifulSoup to extract fields
            else:
                logger.warning("verra_page_blocked", project_id=vid, snippet=html[:200])

        if not leads:
            logger.warning("verra_live_scrape_blocked", country=country)
        return leads

    def health_check(self) -> Dict[str, Any]:
        """Check if Verra scraping is functional."""
        if not self.live_mode:
            return {"status": "demo", "message": "Demo mode active — set LEAD_SCRAPER_MODE=live to enable real scraping"}
        html = self._fetch_project_page("1525")
        if html and "Project Details" in html:
            return {"status": "healthy", "message": "Verra registry reachable"}
        return {"status": "blocked", "message": "Verra registry blocked (Cloudflare/anti-bot). Install Playwright for headless scraping."}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("verra_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            live_leads = self._try_live_scrape(country, status_filter)
            if live_leads:
                leads.extend(live_leads)
                data_source = "live"
            else:
                logger.warning("verra_live_scrape_empty", country=country, falling_back="demo")

        if not leads:
            data_source = "demo"
            for raw in DEMO_VERRA_LEADS:
                if country and raw.get("country") != country:
                    continue
                if status_filter != "all" and raw.get("status") != status_filter:
                    continue
                raw["registry_source"] = self.source
                raw["scraped_at"] = datetime.now(timezone.utc).isoformat()
                leads.append(raw.copy())

        logger.info("verra_scrape_completed", count=len(leads), live_mode=self.live_mode, data_source=data_source)
        # Attach metadata so the API can report per-source status
        for lead in leads:
            lead["_scrape_meta"] = {"source": self.source, "data_source": data_source}
        return leads

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
