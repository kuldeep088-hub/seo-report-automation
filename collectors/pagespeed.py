"""
Collector: Google PageSpeed Insights / Core Web Vitals
Free API — enable "PageSpeed Insights API" in Google Cloud Console.
Set PAGESPEED_API_KEY in .env. Gracefully skips if key not set.
"""

import json
import logging
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

_EMPTY = {
    "mobile":  {"performance_score": None, "lcp": "N/A", "tbt": "N/A", "cls": "N/A", "fcp": "N/A", "speed_index": "N/A"},
    "desktop": {"performance_score": None, "lcp": "N/A", "tbt": "N/A", "cls": "N/A", "fcp": "N/A", "speed_index": "N/A"},
    "url":     "",
    "month":   "",
}


def _get_api_key() -> str:
    return os.environ.get("PAGESPEED_API_KEY", "")


def _fetch(url: str, strategy: str, api_key: str) -> dict:
    params = {"url": url, "strategy": strategy, "key": api_key}
    resp = requests.get(PAGESPEED_API, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _parse(data: dict) -> dict:
    lhr = data.get("lighthouseResult", {})
    cats = lhr.get("categories", {})
    audits = lhr.get("audits", {})

    score = cats.get("performance", {}).get("score")
    perf_score = round(score * 100) if score is not None else None

    def _val(key):
        return audits.get(key, {}).get("displayValue", "N/A")

    return {
        "performance_score": perf_score,
        "lcp":         _val("largest-contentful-paint"),
        "tbt":         _val("total-blocking-time"),
        "cls":         _val("cumulative-layout-shift"),
        "fcp":         _val("first-contentful-paint"),
        "speed_index": _val("speed-index"),
    }


def collect_pagespeed(config: dict, month: str) -> dict:
    api_key = _get_api_key()
    if not api_key or api_key == "your_pagespeed_api_key_here":
        log.warning("PAGESPEED_API_KEY not set — skipping Core Web Vitals collection.")
        result = dict(_EMPTY)
        result["month"] = month
        return result

    url = config["client"].get("pagespeed_url") or config["client"].get("gsc_site_url", "")
    client_id = config["client"]["domain"].replace(".", "_")
    cache = Path("clients") / client_id / "data" / f"pagespeed_{month}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists():
        log.info("PageSpeed cache hit for %s", month)
        return json.loads(cache.read_text(encoding="utf-8"))

    log.info("Fetching PageSpeed data for %s ...", url)
    result = dict(_EMPTY)
    result["url"] = url
    result["month"] = month

    for strategy in ["mobile", "desktop"]:
        try:
            data = _fetch(url, strategy, api_key)
            result[strategy] = _parse(data)
            log.info("PageSpeed %s score: %s", strategy, result[strategy]["performance_score"])
        except Exception as e:
            log.warning("PageSpeed %s fetch failed: %s", strategy, e)

    cache.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
