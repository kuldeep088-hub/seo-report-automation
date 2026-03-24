"""
Collector: Google Search Console Screenshot
Uses Playwright with saved Google session to capture the GSC Performance page.
Saves screenshot to clients/<client_id>/screenshots/gsc_<month>.png

Requires one-time setup: python setup_gsc_browser.py
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)

SESSION_DIR  = Path("credentials/gsc_session")
SCREENSHOT_W = 1400
SCREENSHOT_H = 900


def _month_date_range_ms(month_str: str) -> tuple[str, str]:
    """Returns GSC URL date params in milliseconds epoch format."""
    dt    = datetime.strptime(month_str, "%Y-%m")
    start = dt.replace(day=1)
    end   = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    start_ms = int(start.timestamp() * 1000)
    end_ms   = int(end.timestamp() * 1000)
    return str(start_ms), str(end_ms)


def _build_gsc_url(site_url: str, month_str: str) -> str:
    """Build the GSC Performance page URL with date filter for the report month."""
    start_ms, end_ms = _month_date_range_ms(month_str)
    encoded = quote(site_url, safe="")
    return (
        f"https://search.google.com/search-console/performance/search-analytics"
        f"?resource_id={encoded}"
        f"&num_of_days=28"
        f"&start_date={start_ms}"
        f"&end_date={end_ms}"
    )


def collect_gsc_screenshot(config: dict, month: str) -> str | None:
    """
    Takes a screenshot of the GSC Performance page for the given month.
    Returns the path to the saved screenshot, or None if it failed.
    """
    if not SESSION_DIR.exists():
        log.warning(
            "GSC session not found at '%s'. "
            "Run 'python setup_gsc_browser.py' once to set it up.",
            SESSION_DIR,
        )
        return None

    site_url  = config["client"]["gsc_site_url"]
    client_id = config["client"]["domain"].replace(".", "_")

    out_dir = Path("clients") / client_id / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gsc_{month}.png"

    if out_path.exists():
        log.info("GSC screenshot cache hit for %s", month)
        return str(out_path)

    gsc_url = _build_gsc_url(site_url, month)
    log.info("Taking GSC screenshot for %s ...", month)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                headless=True,
                viewport={"width": SCREENSHOT_W, "height": SCREENSHOT_H},
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            page = browser.new_page()
            page.set_viewport_size({"width": SCREENSHOT_W, "height": SCREENSHOT_H})

            # Navigate to GSC performance page
            page.goto(gsc_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # Dismiss any cookie/consent banners if present
            for selector in [
                "button:has-text('Accept all')",
                "button:has-text('I agree')",
                "button:has-text('Reject all')",
                "[aria-label='Close']",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Wait for the performance chart to load
            try:
                page.wait_for_selector(
                    "[data-metric-type], .ab7Nf, svg.nnLLaf",
                    timeout=15000,
                )
                page.wait_for_timeout(2000)
            except Exception:
                log.warning("GSC chart selector timed out — taking screenshot anyway.")

            # Take full screenshot
            page.screenshot(path=str(out_path), full_page=False)
            browser.close()

        log.info("GSC screenshot saved: %s", out_path)
        return str(out_path)

    except Exception as e:
        log.warning("GSC screenshot failed: %s — skipping.", e)
        return None
