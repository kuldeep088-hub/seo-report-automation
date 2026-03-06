"""Quick connection test for GA4 and GSC."""
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from google.oauth2 import service_account

KEY_FILE = "credentials/google_service_account.json"

# ── Test GA4 ──────────────────────────────────────────────────────────────────
print("Testing GA4...")
try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    client = BetaAnalyticsDataClient(credentials=creds)
    request = RunReportRequest(
        property="properties/355283766",
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
        date_ranges=[DateRange(start_date="2025-02-01", end_date="2025-02-28")],
    )
    response = client.run_report(request)
    print(f"  GA4 OK — {len(response.rows)} channel(s) returned")
    for row in response.rows:
        print(f"    {row.dimension_values[0].value}: {row.metric_values[0].value} sessions")
except Exception as e:
    print(f"  GA4 FAILED: {e}")

# ── Test GSC ──────────────────────────────────────────────────────────────────
print("\nTesting GSC...")
try:
    from google.auth.transport.requests import AuthorizedSession
    from urllib.parse import quote

    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    session = AuthorizedSession(creds)
    site_url = "https://scotle.org"
    encoded = quote(site_url, safe="")
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query"

    resp = session.post(url, json={
        "startDate": "2025-02-01",
        "endDate": "2025-02-28",
        "dimensions": ["query"],
        "rowLimit": 5,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("rows", [])
    print(f"  GSC OK — {len(rows)} keyword(s) returned")
    for r in rows:
        print(f"    '{r['keys'][0]}': {r.get('clicks', 0)} clicks, pos {round(r.get('position', 0), 1)}")
except Exception as e:
    print(f"  GSC FAILED: {e}")
