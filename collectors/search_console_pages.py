"""
Collector: Google Search Console — Landing Pages
Fetches top pages by clicks using dimensions=["page"].
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GSC_API = "https://searchconsole.googleapis.com/webmasters/v3/sites"
TOP_PAGES_LIMIT = 50


def _get_session() -> AuthorizedSession:
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json")
    creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    return AuthorizedSession(creds)


def _month_date_range(month_str: str) -> tuple[str, str]:
    dt = datetime.strptime(month_str, "%Y-%m")
    start = dt.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _prev_month_str(month_str: str) -> str:
    dt = datetime.strptime(month_str, "%Y-%m")
    first = dt.replace(day=1)
    prev = first - timedelta(days=1)
    return prev.strftime("%Y-%m")


def _fetch_from_api(site_url: str, start_date: str, end_date: str) -> dict:
    session = _get_session()
    encoded_site = quote(site_url, safe="")
    url = f"{GSC_API}/{encoded_site}/searchAnalytics/query"
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": TOP_PAGES_LIMIT,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
    }
    response = session.post(url, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_response(response: dict) -> list[dict]:
    pages = []
    for row in response.get("rows", []):
        pages.append({
            "page":        row["keys"][0],
            "clicks":      int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr":         round(row.get("ctr", 0) * 100, 2),
            "position":    round(row.get("position", 0), 1),
        })
    return pages


def collect_landing_pages(config: dict, month: str) -> dict:
    site_url  = config["client"]["gsc_site_url"]
    client_id = config["client"]["domain"].replace(".", "_")
    prev_month = _prev_month_str(month)

    result = {}
    for m in [month, prev_month]:
        cache = Path("clients") / client_id / "data" / f"gsc_pages_{m}.json"
        cache.parent.mkdir(parents=True, exist_ok=True)

        if cache.exists():
            log.info("GSC pages cache hit for %s", m)
            raw = json.loads(cache.read_text(encoding="utf-8"))
        else:
            log.info("Fetching GSC landing pages for %s from API...", m)
            start, end = _month_date_range(m)
            try:
                raw = _fetch_from_api(site_url, start, end)
                cache.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            except Exception as e:
                log.warning("GSC pages fetch failed for %s: %s — skipping.", m, e)
                raw = {}

        result[m] = _parse_response(raw)

    return {"current": result[month], "previous": result[prev_month], "month": month}
