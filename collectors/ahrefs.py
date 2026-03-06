"""
Collector: Ahrefs API v3
Fetches new and lost backlinks for the target domain within the report month.
Returns empty data gracefully if AHREFS_API_KEY is not set.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger(__name__)

AHREFS_BASE_URL = "https://api.ahrefs.com/v3"

_EMPTY_RESULT = {
    "new_backlinks": [],
    "lost_backlinks": [],
    "domain_metrics": {},
    "month": "",
}


def _get_api_key() -> str:
    return os.environ.get("AHREFS_API_KEY", "")


def _month_date_range(month_str: str) -> tuple[str, str]:
    dt = datetime.strptime(month_str, "%Y-%m")
    start = dt.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _fetch_new_backlinks(target: str, date_from: str, date_to: str, limit: int = 50) -> dict:
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Accept": "application/json",
    }
    params = {
        "target": target,
        "mode": "domain",
        "date_from": date_from,
        "date_to": date_to,
        "select": "url_from,domain_rating_source,anchor,url_to,first_seen,is_dofollow",
        "limit": limit,
        "order_by": "domain_rating_source:desc",
    }
    response = requests.get(
        f"{AHREFS_BASE_URL}/site-explorer/new-backlinks",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_lost_backlinks(target: str, date_from: str, date_to: str, limit: int = 50) -> dict:
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Accept": "application/json",
    }
    params = {
        "target": target,
        "mode": "domain",
        "date_from": date_from,
        "date_to": date_to,
        "select": "url_from,domain_rating_source,anchor,url_to,lost_date,is_dofollow",
        "limit": limit,
    }
    response = requests.get(
        f"{AHREFS_BASE_URL}/site-explorer/lost-backlinks",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_domain_metrics(target: str) -> dict:
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Accept": "application/json",
    }
    params = {
        "target": target,
        "select": "domain_rating,backlinks,referring_domains",
    }
    response = requests.get(
        f"{AHREFS_BASE_URL}/site-explorer/domain-rating",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def collect_backlinks(config: dict, month: str) -> dict:
    """
    Returns new backlinks, lost backlinks, and domain metrics.
    Skips gracefully if AHREFS_API_KEY is not configured.
    """
    api_key = _get_api_key()
    if not api_key or api_key == "your_ahrefs_api_key_here":
        log.warning("AHREFS_API_KEY not set — skipping backlink collection.")
        empty = dict(_EMPTY_RESULT)
        empty["month"] = month
        return empty

    target = config["client"]["ahrefs_target"]
    client_id = config["client"]["domain"].replace(".", "_")
    cache_file = Path("clients") / client_id / "data" / f"ahrefs_{month}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if cache_file.exists():
        log.info("Ahrefs cache hit for %s", month)
        return json.loads(cache_file.read_text(encoding="utf-8"))

    log.info("Fetching Ahrefs data for %s from API...", month)
    date_from, date_to = _month_date_range(month)

    try:
        new_raw = _fetch_new_backlinks(target, date_from, date_to)
        lost_raw = _fetch_lost_backlinks(target, date_from, date_to)
        metrics_raw = _fetch_domain_metrics(target)
    except requests.HTTPError as e:
        log.error("Ahrefs API error: %s — skipping backlinks.", e)
        empty = dict(_EMPTY_RESULT)
        empty["month"] = month
        return empty

    result = {
        "new_backlinks": new_raw.get("backlinks", []),
        "lost_backlinks": lost_raw.get("backlinks", []),
        "domain_metrics": metrics_raw,
        "month": month,
    }

    cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
