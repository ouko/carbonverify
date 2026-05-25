"""Gold Standard registry scraper.

Gold Standard API: https://api.goldstandard.org/projects
Note: This endpoint is protected by Cloudflare. Simple HTTP requests are blocked.

To enable live scraping, either:
  1. Use Playwright/Selenium for headless browser automation
  2. Use a proxy/rotating IP service
  3. Contact Gold Standard for API access credentials

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
        "external_id": "GS-6811",
        "project_name": "Mombasa Clean Cooking Initiative",
        "project_developer": "Hivos Impact Investments",
        "developer_contact": "+254 733 456789",
        "developer_email": "kenya@hivos.org",
        "country": "Kenya",
        "region": "Mombasa",
        "methodology": "TPDDTEC_v4",
        "sector": "Household Devices",
        "status": "certified",
        "crediting_period_start": "2021-01-01",
        "crediting_period_end": "2030-12-31",
        "last_verification_date": "2023-11-10",
        "estimated_credits_per_year": 35000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/6811",
        "days_in_status": 580,
    },
    {
        "external_id": "GS-7123",
        "project_name": "Rift Valley LPG Adoption",
        "project_developer": "SafariCarbon Kenya",
        "developer_contact": None,
        "developer_email": "leads@safaricarbon.com",
        "country": "Kenya",
        "region": "Nakuru",
        "methodology": "AMS-II.G",
        "sector": "Energy Efficiency",
        "status": "under_certification",
        "crediting_period_start": "2022-07-01",
        "crediting_period_end": "2031-06-30",
        "last_verification_date": None,
        "estimated_credits_per_year": 15000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/7123",
        "days_in_status": 195,
    },
    {
        "external_id": "GS-5890",
        "project_name": "Coastal Kenya Solar Lighting",
        "project_developer": "SolarNow Carbon",
        "developer_contact": "+254 701 234567",
        "developer_email": "carbon@solar-now.com",
        "country": "Kenya",
        "region": "Kilifi",
        "methodology": "VMR0006",
        "sector": "Energy",
        "status": "certified",
        "crediting_period_start": "2020-06-01",
        "crediting_period_end": "2029-05-31",
        "last_verification_date": "2022-12-01",
        "estimated_credits_per_year": 8000.0,
        "registry_url": "https://registry.goldstandard.org/projects/details/5890",
        "days_in_status": 920,
    },
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://registry.goldstandard.org",
    "Referer": "https://registry.goldstandard.org/",
}


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
                http2=True,
            )
        return self.client

    def _try_live_scrape(self, country: str, status_filter: str) -> List[Dict[str, Any]]:
        logger.info("gold_standard_live_scrape_attempt", country=country)
        url = "https://api.goldstandard.org/projects"
        params = {
            "country": country,
            "size": 50,
            "page": 0,
        }
        client = self._get_client()
        leads = []

        for attempt in range(settings.LEAD_SCRAPER_MAX_RETRIES):
            try:
                time.sleep(self.rate_limit_delay)
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("content", []):
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
        url = "https://api.goldstandard.org/projects"
        client = self._get_client()
        try:
            resp = client.get(url, params={"country": "Kenya", "size": 1}, timeout=10)
            if resp.status_code == 200:
                return {"status": "healthy", "message": "Gold Standard API reachable"}
            if resp.status_code == 403:
                return {"status": "blocked", "message": "Gold Standard blocked by Cloudflare. Use Playwright or proxy rotation."}
            return {"status": "degraded", "message": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def scrape(self, country: str = "Kenya", status_filter: str = "all") -> List[Dict[str, Any]]:
        logger.info("gold_standard_scrape_started", country=country, filter=status_filter, live_mode=self.live_mode)

        leads: List[Dict[str, Any]] = []
        data_source = "demo"

        if self.live_mode:
            live_leads = self._try_live_scrape(country, status_filter)
            if live_leads:
                leads.extend(live_leads)
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
