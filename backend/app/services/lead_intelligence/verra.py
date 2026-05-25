"""Verra registry scraper.

Verra Registry uses a JavaScript-heavy Angular frontend with Cloudflare protection.
Playwright is used to bypass bot detection, but the Angular app is complex and
may not fully render in automated contexts. Falls back to demo data when blocked.
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
        "project_developer": "LTWP Carbon Ltd",
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
        "project_name": "Mau Forest Restoration Phase II",
        "project_developer": "Kenya Forest Service",
        "developer_contact": "+254 20 2345678",
        "developer_email": "carbon@kenyaforestservice.org",
        "country": "Kenya",
        "region": "Mau Complex",
        "methodology": "AR-ACM0003",
        "sector": "Forestry",
        "status": "under_validation",
        "crediting_period_start": "2023-01-01",
        "crediting_period_end": "2053-12-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 45000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/2311",
        "days_in_status": 180,
    },
    {
        "external_id": "VCS-VCU-1899",
        "project_name": "Nairobi BRT Emissions Reduction",
        "project_developer": "Transport Carbon Africa",
        "developer_contact": "+254 722 998877",
        "developer_email": "carbon@transportafrica.org",
        "country": "Kenya",
        "region": "Nairobi",
        "methodology": "VM0055",
        "sector": "Transport",
        "status": "under_verification",
        "crediting_period_start": "2024-01-01",
        "crediting_period_end": "2034-12-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 95000.0,
        "registry_url": "https://registry.verra.org/app/projectDetail/VCS/VCU/1899",
        "days_in_status": 90,
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


def _scrape_verra_with_playwright(country: str) -> List[Dict[str, Any]]:
    """Attempt to scrape Verra using Playwright.

    Verra's Angular app is complex; this is a best-effort approach that
    navigates the search page and tries to extract visible project data.
    Uses the persistent browser singleton to avoid ~40s launch cost.
    """
    try:
        from playwright_stealth import Stealth
        from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser
    except ImportError:
        logger.warning("playwright_not_installed")
        return []

    logger.info("verra_playwright_scrape_start", country=country)
    leads = []

    try:
        browser = _get_or_launch_browser(headless=False)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=DEFAULT_HEADERS["User-Agent"],
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # Navigate to search page
        page.goto(
            "https://registry.verra.org/app/search/VCS/All%20Projects",
            timeout=20000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(10000)

        # Try to interact with filters if they exist
        try:
            country_filter = page.query_selector('[placeholder*="Country"], input[formcontrolname*="country"]')
            if country_filter:
                country_filter.fill(country)
                page.wait_for_timeout(2000)
        except Exception:
            pass

        # Try clicking search
        search_btn = page.query_selector('button[type=submit], .btn-search')
        if search_btn:
            search_btn.click()
            page.wait_for_timeout(8000)

        # Extract any visible project rows
        html = page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Look for project links in the rendered DOM
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/projectDetail/VCS/VCU/" in href:
                project_id = href.split("/")[-1]
                name = link.get_text(strip=True)
                if name and project_id:
                    leads.append({
                        "external_id": f"VCS-VCU-{project_id}",
                        "project_name": name,
                        "project_developer": None,
                        "developer_contact": None,
                        "developer_email": None,
                        "country": country,
                        "region": None,
                        "methodology": None,
                        "sector": None,
                        "status": "unknown",
                        "crediting_period_start": None,
                        "crediting_period_end": None,
                        "last_verification_date": None,
                        "estimated_credits_per_year": None,
                        "registry_url": f"https://registry.verra.org/app/projectDetail/VCS/VCU/{project_id}",
                        "days_in_status": None,
                    })

        context.close()
    except Exception as exc:
        logger.error("verra_playwright_failed", error=str(exc))

    logger.info("verra_playwright_scrape_complete", count=len(leads))
    return leads


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

    def health_check(self) -> Dict[str, Any]:
        """Check if Verra scraping is functional."""
        if not self.live_mode:
            return {"status": "demo", "message": "Demo mode active — set LEAD_SCRAPER_MODE=live to enable real scraping"}

        # Try Playwright first
        try:
            from playwright_stealth import Stealth
            from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser

            browser = _get_or_launch_browser(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            page.goto(
                "https://registry.verra.org/app/search/VCS/All%20Projects",
                timeout=20000,
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(5000)
            html = page.content()
            context.close()
            if "Project Search" in html or "Verified Carbon Standard" in html:
                return {"status": "healthy", "message": "Verra registry reachable via Playwright"}
        except Exception as exc:
            logger.warning("verra_playwright_health_failed", error=str(exc))

        return {"status": "blocked", "message": "Verra registry blocked. Angular app requires advanced Playwright interaction."}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("verra_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            live_leads = _scrape_verra_with_playwright(country)
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
        for lead in leads:
            lead["_scrape_meta"] = {"source": self.source, "data_source": data_source}
        return leads

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
