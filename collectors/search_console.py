"""
Collector: Google Search Console (GSC)
Uses AuthorizedSession (requests-based) instead of httplib2.
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
TOP_KEYWORDS_LIMIT = 50


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
        "dimensions": ["query"],
        "rowLimit": TOP_KEYWORDS_LIMIT,
        "orderBy": [{"fieldName": "impressions", "sortOrder": "DESCENDING"}],
    }

    response = session.post(url, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_response(response: dict) -> list[dict]:
    keywords = []
    for row in response.get("rows", []):
        keywords.append({
            "keyword": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0) * 100, 2),
            "position": round(row.get("position", 0), 1),
        })
    return keywords


def collect_keywords(config: dict, month: str) -> dict:
    site_url = config["client"]["gsc_site_url"]
    client_id = config["client"]["domain"].replace(".", "_")
    prev_month = _prev_month_str(month)

    result = {}
    for m in [month, prev_month]:
        cache = Path("clients") / client_id / "data" / f"gsc_{m}.json"
        cache.parent.mkdir(parents=True, exist_ok=True)

        if cache.exists():
            log.info("GSC cache hit for %s", m)
            raw = json.loads(cache.read_text(encoding="utf-8"))
        else:
            log.info("Fetching GSC data for %s from API...", m)
            start, end = _month_date_range(m)
            raw = _fetch_from_api(site_url, start, end)
            cache.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        result[m] = _parse_response(raw)

    return {"current": result[month], "previous": result[prev_month], "month": month}
