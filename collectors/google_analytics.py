"""
Collector: Google Analytics 4 (GA4)
Uses the google-analytics-data client library (gRPC/requests, no httplib2).
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_client():
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json")
    creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    return BetaAnalyticsDataClient(credentials=creds)


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


def _fetch_from_api(property_id: str, start_date: str, end_date: str) -> dict:
    client = _get_client()
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="newUsers"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
    )
    response = client.run_report(request)

    # Serialize to plain dict for caching
    rows = []
    for row in response.rows:
        rows.append({
            "dimensionValues": [{"value": dv.value} for dv in row.dimension_values],
            "metricValues": [{"value": mv.value} for mv in row.metric_values],
        })
    return {"rows": rows}


def _parse_response(response: dict) -> dict:
    rows = response.get("rows", [])
    channels = {}
    for row in rows:
        channel = row["dimensionValues"][0]["value"]
        metrics = row["metricValues"]
        channels[channel] = {
            "sessions": int(metrics[0]["value"]),
            "new_users": int(metrics[1]["value"]),
            "bounce_rate": round(float(metrics[2]["value"]) * 100, 2),
            "avg_session_duration_sec": round(float(metrics[3]["value"]), 1),
        }
    organic = channels.get("Organic Search", {
        "sessions": 0, "new_users": 0, "bounce_rate": 0, "avg_session_duration_sec": 0
    })
    total_sessions = sum(c["sessions"] for c in channels.values())
    return {
        "organic": organic,
        "all_channels": channels,
        "total_sessions": total_sessions,
    }


def collect_traffic(config: dict, month: str) -> dict:
    client_id = config["client"]["domain"].replace(".", "_")
    property_id = config["client"]["ga4_property_id"]
    prev_month = _prev_month_str(month)

    result = {}
    for m in [month, prev_month]:
        cache = Path("clients") / client_id / "data" / f"ga4_{m}.json"
        cache.parent.mkdir(parents=True, exist_ok=True)

        if cache.exists():
            log.info("GA4 cache hit for %s", m)
            raw = json.loads(cache.read_text(encoding="utf-8"))
        else:
            log.info("Fetching GA4 data for %s from API...", m)
            start, end = _month_date_range(m)
            raw = _fetch_from_api(property_id, start, end)
            cache.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        result[m] = _parse_response(raw)

    return {"current": result[month], "previous": result[prev_month], "month": month}
