"""Gold Standard registry scraper.

Gold Standard (registry.goldstandard.org) uses Cloudflare bot protection.
The public API now requires authentication. Playwright is used as a best-effort
attempt to access project data; falls back to demo data when blocked.
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

DEMO_GS_LEADS: List[Dict[str, Any]] = [
    {
        "external_id": "GS-7542",
        "project_name": "Kisumu Biogas Program",
        "project_developer": "Biogas Solutions East Africa",
        "developer_contact": "+254 712 345678",
        "developer_email": "carbon@biogas-ea.org",
        "country": "Kenya",
        "region": "Kisumu",
        "methodology": "VM0050",
        "sector": "Clean Cooking",
        "status": "under_certification",
        "crediting_period_start": "2023-03-01",
        "crediting_period_end": "2033-02-28",
        "last_verification_date": None,
        "estimated_credits_per_year": 22000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/7542",
        "days_in_status": 310,
    },
    {
        "external_id": "GS-8912",
        "project_name": "Nakuru Reforestation Initiative",
        "project_developer": "Green Belt Movement",
        "developer_contact": "+254 733 987654",
        "developer_email": "carbon@greenbelt.or.ke",
        "country": "Kenya",
        "region": "Nakuru",
        "methodology": "AR-ACM0003",
        "sector": "Forestry",
        "status": "under_validation",
        "crediting_period_start": "2022-08-01",
        "crediting_period_end": "2042-07-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 8500.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/8912",
        "days_in_status": 520,
    },
    {
        "external_id": "GS-4451",
        "project_name": "Mombasa Solar Mini-Grid",
        "project_developer": "Rural Electrification Authority",
        "developer_contact": "+254 20 3456789",
        "developer_email": "carbon@rea.co.ke",
        "country": "Kenya",
        "region": "Mombasa",
        "methodology": "VMR0006",
        "sector": "Energy",
        "status": "registered",
        "crediting_period_start": "2021-01-01",
        "crediting_period_end": "2031-12-31",
        "last_verification_date": "2023-05-15",
        "estimated_credits_per_year": 12000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/4451",
        "days_in_status": 620,
    },
    {
        "external_id": "GS-2288",
        "project_name": "Meru Wind Farm Phase II",
        "project_developer": "Meru Wind Power Ltd",
        "developer_contact": "+254 722 556677",
        "developer_email": "info@meruwind.co.ke",
        "country": "Kenya",
        "region": "Meru",
        "methodology": "VMR0006",
        "sector": "Energy",
        "status": "under_certification",
        "crediting_period_start": "2022-01-01",
        "crediting_period_end": "2042-12-31",
        "last_verification_date": None,
        "estimated_credits_per_year": 185000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/2288",
        "days_in_status": 275,
    },
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _scrape_gold_standard_with_playwright(country: str) -> List[Dict[str, Any]]:
    """Attempt to scrape Gold Standard using Playwright.

    The Gold Standard registry requires authenticated API access.
    Playwright navigates the public project listing page as a fallback.
    Uses the persistent browser singleton to avoid ~40s launch cost.
    """
    try:
        from playwright_stealth import Stealth
        from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser
    except ImportError:
        logger.warning("playwright_not_installed")
        return []

    logger.info("gold_standard_playwright_scrape_start", country=country)
    leads = []

    try:
        browser = _get_or_launch_browser(headless=False)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=DEFAULT_HEADERS["User-Agent"],
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        page.goto(
            "https://registry.goldstandard.org/projects",
            timeout=20000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(5000)

        html = page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Look for project cards or links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/projects/details/" in href:
                project_id = href.split("/")[-1]
                name = link.get_text(strip=True)
                if name and project_id and len(name) > 3:
                    leads.append({
                        "external_id": f"GS-{project_id}",
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
                        "registry_url": f"https://registry.goldstandard.org/projects/details/{project_id}",
                        "days_in_status": None,
                    })

        context.close()
    except Exception as exc:
        logger.error("gold_standard_playwright_failed", error=str(exc))

    logger.info("gold_standard_playwright_scrape_complete", count=len(leads))
    return leads


class GoldStandardScraper(BaseRegistryScraper):
    source = "gold_standard"

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
        """Attempt httpx-based live scrape. Returns empty list if blocked."""
        logger.info("gold_standard_live_scrape_attempt", country=country)
        url = "https://api.goldstandard.org/projects"
        client = self._get_client()

        for attempt in range(settings.LEAD_SCRAPER_MAX_RETRIES):
            try:
                time.sleep(self.rate_limit_delay)
                resp = client.get(
                    url,
                    params={"country": country, "size": 50, "page": 0},
                    timeout=settings.LEAD_SCRAPER_REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("content", []) if isinstance(data, dict) else data
                    leads = []
                    for item in items:
                        lead = {
                            "external_id": item.get("id"),
                            "project_name": item.get("name"),
                            "project_developer": item.get("developer", {}).get("name"),
                            "developer_email": item.get("developer", {}).get("email"),
                            "country": item.get("country"),
                            "region": item.get("region"),
                            "methodology": item.get("methodology"),
                            "sector": item.get("sector"),
                            "status": item.get("status", "").lower().replace(" ", "_"),
                            "crediting_period_start": item.get("creditingPeriodStart"),
                            "crediting_period_end": item.get("creditingPeriodEnd"),
                            "estimated_credits_per_year": item.get("estimatedAnnualEmissionReductions"),
                            "registry_url": f"https://registry.goldstandard.org/projects/details/{item.get('id')}",
                            "registry_source": self.source,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                        leads.append(lead)
                    logger.info("gold_standard_live_scrape_success", count=len(leads))
                    return leads
                elif resp.status_code == 403:
                    logger.warning("gold_standard_blocked_by_cloudflare", attempt=attempt)
                    break
                else:
                    logger.warning("gold_standard_fetch_failed", status=resp.status_code, body=resp.text[:200])
            except Exception as exc:
                logger.warning("gold_standard_fetch_error", attempt=attempt, error=str(exc))
                time.sleep(settings.LEAD_SCRAPER_RETRY_DELAY)

        logger.warning("gold_standard_live_scrape_failed", country=country)
        return []

    def health_check(self) -> Dict[str, Any]:
        if not self.live_mode:
            return {"status": "demo", "message": "Demo mode active — set LEAD_SCRAPER_MODE=live to enable real scraping"}

        # Try Playwright health check
        try:
            from playwright_stealth import Stealth
            from app.services.lead_intelligence.playwright_utils import _get_or_launch_browser

            browser = _get_or_launch_browser(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            page.goto(
                "https://registry.goldstandard.org/projects",
                timeout=20000,
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(5000)
            html = page.content()
            context.close()
            if "project" in html.lower():
                return {"status": "healthy", "message": "Gold Standard registry reachable via Playwright"}
        except Exception as exc:
            logger.warning("gold_standard_playwright_health_failed", error=str(exc))

        return {"status": "blocked", "message": "Gold Standard requires authenticated API or manual access."}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("gold_standard_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            # Try httpx first
            live_leads = self._try_live_scrape(country, status_filter)
            if live_leads:
                leads.extend(live_leads)
                data_source = "live"
            else:
                # Try Playwright fallback
                pw_leads = _scrape_gold_standard_with_playwright(country)
                if pw_leads:
                    for lead in pw_leads:
                        lead["registry_source"] = self.source
                        lead["scraped_at"] = datetime.now(timezone.utc).isoformat()
                    leads.extend(pw_leads)
                    data_source = "live"
                else:
                    logger.warning("gold_standard_live_scrape_empty", country=country, falling_back="demo")

        if not leads:
            data_source = "demo"
            for raw in DEMO_GS_LEADS:
                if country and raw.get("country") != country:
                    continue
                if status_filter != "all" and raw.get("status") != status_filter:
                    continue
                raw_copy = raw.copy()
                raw_copy["registry_source"] = self.source
                raw_copy["scraped_at"] = datetime.now(timezone.utc).isoformat()
                leads.append(raw_copy)

        logger.info("gold_standard_scrape_completed", count=len(leads), live_mode=self.live_mode, data_source=data_source)
        for lead in leads:
            lead["_scrape_meta"] = {"source": self.source, "data_source": data_source}
        return leads

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
