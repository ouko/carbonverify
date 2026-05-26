"""Playwright utilities for bypassing anti-bot protection on carbon registries."""

import random
import time
import threading
from typing import Optional, Dict, Any, List

from playwright.sync_api import sync_playwright, Page, Browser, Response, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

from app.core.logging import get_logger

logger = get_logger(__name__)

from app.config import get_settings

_settings = get_settings()
# Proxy rotation support
PROXY_URL = getattr(_settings, "PROXY_URL", "")
# Production flag forces headless for security
SCRAPER_FORCE_HEADLESS = getattr(_settings, "SCRAPER_FORCE_HEADLESS", False)

# User-agent rotation
_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

_CUSTOM_AGENTS = [a.strip() for a in getattr(_settings, "SCRAPER_USER_AGENTS", "").split(",") if a.strip()]
USER_AGENTS = _CUSTOM_AGENTS if _CUSTOM_AGENTS else _DEFAULT_USER_AGENTS

# Persistent browser instance to avoid ~40s launch cost per scrape
_browser_instance: Optional[Browser] = None
_playwright_instance = None
_browser_lock = threading.Lock()


def _get_or_launch_browser(headless: bool = False) -> Browser:
    """Get or launch a persistent stealth Chromium browser."""
    global _browser_instance, _playwright_instance
    # In production/containerized environments, always force headless
    effective_headless = headless or SCRAPER_FORCE_HEADLESS
    with _browser_lock:
        if _browser_instance is None or _browser_instance.is_connected() is False:
            _playwright_instance = sync_playwright().start()
            launch_kwargs = {
                "headless": effective_headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }
            if PROXY_URL:
                launch_kwargs["proxy"] = {"server": PROXY_URL}
                logger.info("playwright_proxy_configured", proxy=PROXY_URL)
            _browser_instance = _playwright_instance.chromium.launch(**launch_kwargs)
            logger.info("playwright_browser_launched", headless=effective_headless)
        return _browser_instance


def close_persistent_browser() -> None:
    """Close the persistent browser instance."""
    global _browser_instance, _playwright_instance
    with _browser_lock:
        if _browser_instance:
            try:
                _browser_instance.close()
            except Exception:
                pass
            _browser_instance = None
        if _playwright_instance:
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = None
        logger.info("playwright_browser_closed")


def _pick_user_agent() -> str:
    """Return a random user agent from the rotation list."""
    return random.choice(USER_AGENTS)


def _new_stealth_page(browser: Browser, user_agent: Optional[str] = None) -> Page:
    """Create a new page with stealth mode enabled."""
    context = browser.new_context(
        user_agent=user_agent or _pick_user_agent(),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = context.new_page()
    Stealth().apply_stealth_sync(page)
    return page


def playwright_fetch(
    url: str,
    wait_for: Optional[str] = None,
    wait_time: float = 3.0,
    intercept_api: Optional[str] = None,
    headless: bool = True,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> Dict[str, Any]:
    """Fetch a URL using Playwright to bypass bot protection.

    Args:
        url: The URL to navigate to.
        wait_for: A CSS selector to wait for before extracting content.
        wait_time: Extra seconds to wait after page load.
        intercept_api: If provided, intercept XHR/fetch requests matching this URL substring
                       and return the JSON response body instead of HTML.
        headless: Whether to run headless.
        max_retries: Number of retries on timeout or proxy failure.
        retry_delay: Base delay between retries (exponential backoff).

    Returns:
        Dict with keys:
            - html: The rendered page HTML (if intercept_api not matched).
            - json: The intercepted API JSON (if intercept_api matched).
            - status: HTTP status code.
            - url: Final URL after redirects.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        browser = _get_or_launch_browser(headless=headless)
        api_response: Optional[Dict[str, Any]] = None
        page = None

        try:
            page = _new_stealth_page(browser)

            # Optional: intercept API calls
            if intercept_api:
                def handle_response(response: Response):
                    nonlocal api_response
                    if intercept_api in response.url and response.status == 200:
                        try:
                            api_response = response.json()
                        except Exception:
                            pass

                page.on("response", handle_response)

            logger.info("playwright_navigating", url=url, attempt=attempt)
            response = page.goto(url, wait_until="networkidle", timeout=60000)
            status = response.status if response else 0

            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=15000)
                except Exception:
                    logger.warning("playwright_wait_for_timeout", selector=wait_for, url=url)

            if wait_time:
                time.sleep(wait_time)

            final_url = page.url

            if api_response:
                result = {
                    "json": api_response,
                    "status": status,
                    "url": final_url,
                }
            else:
                html = page.content()
                result = {
                    "html": html,
                    "status": status,
                    "url": final_url,
                }

            logger.info("playwright_fetch_complete", url=url, status=status, has_json=api_response is not None)
            return result

        except PlaywrightTimeoutError as exc:
            last_error = exc
            logger.warning("playwright_fetch_timeout", url=url, attempt=attempt, max_retries=max_retries)
        except Exception as exc:
            last_error = exc
            logger.warning("playwright_fetch_error", url=url, attempt=attempt, error=str(exc))

        finally:
            # Don't close persistent browser — just close the page context
            if page:
                try:
                    page.context.close()
                except Exception:
                    pass

        if attempt < max_retries:
            sleep_time = retry_delay * (2 ** (attempt - 1))
            logger.info("playwright_fetch_retry", url=url, attempt=attempt, sleep=sleep_time)
            time.sleep(sleep_time)

    logger.error("playwright_fetch_failed", url=url, error=str(last_error), attempts=max_retries)
    return {"html": "", "status": 0, "url": url, "error": str(last_error)}


def playwright_fetch_multiple(
    urls: List[str],
    wait_for: Optional[str] = None,
    wait_time: float = 2.0,
    headless: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch multiple URLs reusing the persistent browser instance."""
    browser = _get_or_launch_browser(headless=headless)
    results = []

    for url in urls:
        page = None
        try:
            page = _new_stealth_page(browser)
            logger.info("playwright_navigating", url=url)
            response = page.goto(url, wait_until="networkidle", timeout=60000)
            status = response.status if response else 0

            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=10000)
                except Exception:
                    pass

            if wait_time:
                time.sleep(wait_time)

            html = page.content()
            results.append({"html": html, "status": status, "url": page.url})
        except Exception as exc:
            logger.error("playwright_fetch_failed", url=url, error=str(exc))
            results.append({"html": "", "status": 0, "url": url, "error": str(exc)})
        finally:
            if page:
                try:
                    page.context.close()
                except Exception:
                    pass

    return results
