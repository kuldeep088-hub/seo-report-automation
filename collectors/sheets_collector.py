"""
Collector: Google Sheets — Blog Posts & Business Listings
Reads Platform | Link data from month-specific tabs in two Google Sheets.

Sheet setup:
  - Each sheet has tabs named: "January Backlinks", "February Backlinks", etc.
  - Columns (detected by header): Platform | Link  (case-insensitive, partial match)
  - Share each sheet with the OAuth account (or the service account as fallback).

Config keys  (clients/<id>/config.yaml  →  report:):
  google_sheet_blog_id:     "<Google Sheet ID for Blog Posts>"
  google_sheet_listings_id: "<Google Sheet ID for Business Listings>"
"""

import logging
import os
from datetime import datetime

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

OAUTH_TOKEN_FILE = os.environ.get("GOOGLE_OAUTH_TOKEN_FILE", "credentials/oauth_token.json")
_PLACEHOLDER     = "YOUR_GOOGLE_SHEET_ID_HERE"


def _get_credentials():
    """Prefer OAuth user credentials; fall back to service account."""
    if os.path.exists(OAUTH_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(OAUTH_TOKEN_FILE, "w") as fh:
                fh.write(creds.to_json())
        return creds
    key_file = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json"
    )
    return service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)


def _tab_name(month: str) -> str:
    """'2025-02' → 'February Backlinks'"""
    return datetime.strptime(month, "%Y-%m").strftime("%B Backlinks")


def _col_index(header: list, *candidates) -> int:
    """Return the first column index whose header contains any of the candidate substrings."""
    for i, h in enumerate(header):
        for cand in candidates:
            if cand.lower() in h.strip().lower():
                return i
    return -1


def _list_sheet_tabs(service, sheet_id: str) -> list:
    """Return all tab titles in the spreadsheet."""
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def _resolve_tab(service, sheet_id: str, desired: str) -> str:
    """
    Return the actual tab name that best matches `desired`.
    Tries exact match first, then case-insensitive, then month-word match.
    Raises ValueError listing available tabs if nothing matches.
    """
    tabs = _list_sheet_tabs(service, sheet_id)

    # 1. Exact match
    if desired in tabs:
        return desired

    # 2. Case-insensitive match
    desired_lower = desired.lower()
    for t in tabs:
        if t.lower() == desired_lower:
            return t

    # 3. Month-word match (e.g. "February" found anywhere in tab name)
    month_word = desired.split()[0].lower()        # "february"
    for t in tabs:
        if month_word in t.lower():
            return t

    raise ValueError(
        f"Tab '{desired}' not found. Available tabs: {tabs}"
    )


def _fetch_sheet_tab(service, sheet_id: str, tab: str) -> list:
    """
    Read all rows from a named tab, resolving the actual tab name first.
    Returns list of raw row lists (strings).
    Raises on API errors so the caller can handle gracefully.
    """
    actual_tab = _resolve_tab(service, sheet_id, tab)
    if actual_tab != tab:
        log.info("Tab '%s' not found — using '%s' instead.", tab, actual_tab)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{actual_tab}'!A:Z",
    ).execute()
    return result.get("values", [])


def _collect_links(config: dict, month: str, config_key: str, label: str) -> dict:
    """
    Generic helper: reads a sheet + month tab, returns
    {"items": [{"platform": ..., "link": ...}, ...], "total": N}.
    """
    empty = {"items": [], "total": 0}

    raw_id = config.get("report", {}).get(config_key, "").strip()
    if not raw_id or raw_id == _PLACEHOLDER:
        log.warning("%s sheet ID not configured (%s) — skipping.", label, config_key)
        return empty
    # Strip any accidentally-pasted URL suffix (e.g. ".../edit?gid=...")
    sheet_id = raw_id.split("/")[0].split("?")[0].strip()

    tab = _tab_name(month)
    try:
        service = build("sheets", "v4", credentials=_get_credentials())
        rows    = _fetch_sheet_tab(service, sheet_id, tab)
    except Exception as exc:
        log.warning("Could not fetch %s sheet (tab '%s'): %s", label, tab, exc)
        return empty

    if not rows:
        log.info("%s sheet tab '%s' is empty.", label, tab)
        return empty

    # Detect header row — find the row containing "platform" or "link"
    header_idx = 0
    col_platform = col_link = -1
    for i, row in enumerate(rows[:5]):          # scan first 5 rows for a header
        cp = _col_index(row, "platform", "site", "website", "source", "name")
        cl = _col_index(row, "link", "url", "href")
        if cp >= 0 or cl >= 0:
            header_idx   = i
            col_platform = cp
            col_link     = cl
            break

    # If no proper header found, assume col 0 = platform, col 1 = link
    if col_platform < 0 and col_link < 0:
        col_platform, col_link = 0, 1

    items = []
    for row in rows[header_idx + 1:]:
        platform = row[col_platform].strip() if col_platform >= 0 and col_platform < len(row) else ""
        link     = row[col_link].strip()     if col_link     >= 0 and col_link     < len(row) else ""

        # Skip blank / header-looking rows
        if not platform and not link:
            continue
        if platform.lower() in ("platform", "site", "name", "source"):
            continue

        items.append({
            "platform": platform or "-",
            "link":     link     or "-",
        })

    log.info("%s: fetched %d links from tab '%s'.", label, len(items), tab)
    return {"items": items, "total": len(items)}


# ── Public API ────────────────────────────────────────────────────────────────

def collect_blog_posts(config: dict, month: str) -> dict:
    """Read blog posts from the Blog Posting Sheet for the given month."""
    return _collect_links(config, month, "google_sheet_blog_id", "Blog Posts")


def collect_business_listings(config: dict, month: str) -> dict:
    """Read business listings from the Business Listings Sheet for the given month."""
    return _collect_links(config, month, "google_sheet_listings_id", "Business Listings")
