"""
Exporter: Google Docs
Creates a fully formatted 9-section Google Doc SEO report with data tables and charts.
Credentials (in order of preference):
  1. credentials/oauth_token.json  (OAuth2 user credentials — run setup_oauth.py once)
  2. GOOGLE_SERVICE_ACCOUNT_FILE env var / credentials/google_service_account.json
"""

import io
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

OAUTH_TOKEN_FILE = os.environ.get("GOOGLE_OAUTH_TOKEN_FILE", "credentials/oauth_token.json")

# Chart marker prefix used in the document body to locate insertion points
_CHART_PREFIX = "[CHART:"
_CHART_SUFFIX = "]"


def _get_credentials():
    if os.path.exists(OAUTH_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(OAUTH_TOKEN_FILE, "w") as fh:
                fh.write(creds.to_json())
        return creds
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json")
    return service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)


def _format_month_display(month_str: str) -> str:
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.strftime("%B %Y")


def _format_month_subtitle(month_str: str) -> str:
    """Returns '(February - 2025)' style subtitle."""
    dt = datetime.strptime(month_str, "%Y-%m")
    return f"({dt.strftime('%B')} - {dt.year})"


def _format_doc_title(client_id: str, month_str: str) -> str:
    """Returns 'SEO_Monthly_Report_SCOTLE_February_2026'."""
    dt = datetime.strptime(month_str, "%Y-%m")
    month_slug = dt.strftime("%B_%Y")
    return f"SEO_Monthly_Report_{client_id.upper()}_{month_slug}"


def _get_or_create_subfolder(drive_service, parent_id: str, folder_name: str) -> str:
    """Find or create a subfolder inside parent_id. Returns the subfolder's Drive ID."""
    safe_name = folder_name.replace("'", "\\'")
    query = (
        f"mimeType='application/vnd.google-apps.folder'"
        f" and name='{safe_name}'"
        f" and '{parent_id}' in parents"
        f" and trashed=false"
    )
    results = drive_service.files().list(
        q=query, fields="files(id, name)", supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder_meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = drive_service.files().create(
        body=folder_meta, fields="id", supportsAllDrives=True
    ).execute()
    log.info("Created Drive subfolder '%s' in parent %s", folder_name, parent_id)
    return created["id"]


# ── Brand colours ─────────────────────────────────────────────────────────────
_BLUE_RGB    = {"red": 47 / 255,  "green": 128 / 255, "blue": 237 / 255}  # #2F80ED
_SEPARATOR   = "_" * 56 + "\n"

# Highlight box background colours
_INSIGHT_BG  = {"red": 0.922, "green": 0.953, "blue": 0.992}   # #EBF3FD light blue
_GROWTH_BG   = {"red": 0.902, "green": 0.957, "blue": 0.918}   # #E6F4EA light green
_WARNING_BG  = {"red": 0.996, "green": 0.969, "blue": 0.878}   # #FEF7E0 light amber

_H1_TEXT_STYLE = {
    "bold":               True,
    "fontSize":           {"magnitude": 16, "unit": "PT"},
    "foregroundColor":    {"color": {"rgbColor": _BLUE_RGB}},
    "weightedFontFamily": {"fontFamily": "Arial"},
}
_H2_TEXT_STYLE = {
    "bold":               True,
    "fontSize":           {"magnitude": 13, "unit": "PT"},
    "foregroundColor":    {"color": {"rgbColor": _BLUE_RGB}},
    "weightedFontFamily": {"fontFamily": "Arial"},
}
_TITLE_TEXT_STYLE = {
    "bold":               True,
    "fontSize":           {"magnitude": 22, "unit": "PT"},
    "foregroundColor":    {"color": {"rgbColor": _BLUE_RGB}},
    "weightedFontFamily": {"fontFamily": "Arial"},
}
_HEADER_CELL_STYLE = {
    "bold":            True,
    "foregroundColor": {"color": {"rgbColor": _BLUE_RGB}},
}
_BOX_TITLE_STYLE = {
    "bold":            True,
    "fontSize":        {"magnitude": 10, "unit": "PT"},
    "foregroundColor": {"color": {"rgbColor": _BLUE_RGB}},
}


def _u(s: str) -> int:
    """UTF-16 code unit length — matches the index units used by the Google Docs API."""
    return len(s.encode("utf-16-le")) // 2


def _sec_to_duration(seconds) -> str:
    try:
        s = int(float(seconds))
        m, s = divmod(s, 60)
        return f"{m}m {s:02d}s"
    except (TypeError, ValueError):
        return str(seconds)


def _pct_str(val) -> str:
    try:
        return f"{float(val):+.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _goal_status(actual, target) -> str:
    try:
        return "On Track" if float(actual) >= float(target) else "Behind"
    except (TypeError, ValueError):
        return "N/A"


# ── Document content builder ──────────────────────────────────────────────────

def _build_text_requests(context: dict, sections: dict, client_id: str):
    """
    Builds all insertText + updateParagraphStyle + updateTextStyle requests.

    Returns (requests, table_specs, chart_markers) where:
      - table_specs: list of {index, headers, rows} sorted DESCENDING
      - chart_markers: list of {name, marker_text, index} in document order
    """
    domain        = context["client"]["domain"]
    month_display = _format_month_display(context["report_month"])
    t       = context["traffic"]
    k       = context["keywords"]
    b       = context["backlinks"]
    targets = context.get("targets", {})

    requests     = []
    table_specs  = []
    chart_markers = []
    pos = 1

    def ins(text: str, style: str = None, text_style: dict = None):
        """Insert text, optionally set paragraph style and/or character text style."""
        nonlocal pos
        if not text:
            return
        requests.append({"insertText": {"location": {"index": pos}, "text": text}})
        start, end = pos, pos + _u(text)
        if style:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            })
        if text_style:
            # Apply to text only, not the trailing newline (end - 1 in UTF-16 units)
            style_end = end - 1 if text.endswith("\n") else end
            if style_end > start:
                fields = ",".join(text_style.keys())
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": style_end},
                        "textStyle": text_style,
                        "fields": fields,
                    }
                })
        pos = end

    def h1(title: str):
        """Main section heading: blue, 18 pt, bold + separator line."""
        ins(title + "\n", style="HEADING_1", text_style=_H1_TEXT_STYLE)
        ins(_SEPARATOR)

    def h2(title: str):
        """Sub-section heading: blue, 14 pt, bold."""
        ins(title + "\n", style="HEADING_2", text_style=_H2_TEXT_STYLE)

    def table(headers: list, rows: list):
        table_specs.append({"index": pos, "headers": headers, "rows": rows})
        ins("\n")

    def box(title: str, items: list, color: str = "insight"):
        """Coloured highlight box (Key Insights, Growth Opportunities, etc.)."""
        bg_map = {"insight": _INSIGHT_BG, "growth": _GROWTH_BG, "warning": _WARNING_BG}
        bullet_lines = "\n".join(f"\u2022  {item}" for item in items)
        content = f"{title}\n{bullet_lines}"
        table_specs.append({
            "index":         pos,
            "headers":       [],
            "rows":          [[content]],
            "is_highlight":  True,
            "box_color":     bg_map.get(color, _INSIGHT_BG),
            "box_title_len": _u(title),
        })
        ins("\n")

    def mark(name: str):
        """Placeholder paragraph replaced by a chart image later."""
        marker_text = f"{_CHART_PREFIX}{name}{_CHART_SUFFIX}"
        chart_markers.append({"name": name, "marker_text": marker_text, "index": pos})
        ins(marker_text + "\n")

    # ── Title ─────────────────────────────────────────────────────────────────
    client_display = context["client"]["name"].upper()
    ins(f"SEO Monthly Report - {client_display}\n", style="TITLE",
        text_style=_TITLE_TEXT_STYLE)
    ins(_format_month_subtitle(context["report_month"]) + "\n", style="SUBTITLE")
    ins("\n")

    # ── 1. Executive Summary ─────────────────────────────────────────────────
    h1("1. Executive Summary")
    ins(sections["executive_summary"] + "\n\n")
    box("KEY METRICS AT A GLANCE", [
        f"Organic Sessions: {t['organic_sessions']:,}  ({_pct_str(t['organic_sessions_change_pct'])} vs last month)",
        f"Organic Clicks (GSC): {k['total_clicks']:,}  ({_pct_str(k['clicks_change_pct'])} vs last month)",
        f"Impressions (GSC): {k['total_impressions']:,}  ({_pct_str(k['impressions_change_pct'])} vs last month)",
        f"Keywords in Top 10: {k['keywords_in_top_10']}   |   Keywords in Top 3: {k['keywords_in_top_3']}",
        f"Domain Rating: {b['domain_rating']}   |   New Backlinks this month: {b['new_backlinks_count']}",
    ], color="insight")
    ins("\n")

    # ── 2. Search Console Performance ────────────────────────────────────────
    h1("2. Search Console Performance")
    ins(sections["keyword_rankings"] + "\n\n")
    h2("Key Metrics")
    table(
        headers=["Metric", "Current", "Previous", "Change"],
        rows=[
            ["Organic Clicks",    f"{k['total_clicks']:,}",       f"{k['total_clicks_prev']:,}",      _pct_str(k["clicks_change_pct"])],
            ["Impressions",       f"{k['total_impressions']:,}",   f"{k['total_impressions_prev']:,}", _pct_str(k["impressions_change_pct"])],
            ["Keywords (Top 10)", str(k["keywords_in_top_10"]),    "-", "-"],
            ["Keywords (Top 3)",  str(k["keywords_in_top_3"]),     "-", "-"],
            ["New Keywords",      str(k["new_keywords_count"]),    "-", "-"],
            ["Lost Keywords",     str(k["lost_keywords_count"]),   "-", "-"],
        ],
    )
    h2("Clicks vs Impressions Trend")
    mark("clicks_impressions")
    ins("\n")
    box("KEY INSIGHTS", [
        f"Organic clicks {_pct_str(k['clicks_change_pct'])} compared to last month",
        f"Impressions {_pct_str(k['impressions_change_pct'])} compared to last month",
        f"{k['new_keywords_count']} new keywords entered Google rankings this month",
        f"{k['lost_keywords_count']} keywords dropped from rankings this month",
        f"Currently {k['keywords_in_top_10']} keywords ranked in the top 10 positions",
    ], color="insight")
    ins("\n")

    # ── 3. GA4 Traffic Overview ───────────────────────────────────────────────
    h1("3. GA4 Traffic Overview")
    ins(sections["traffic_analysis"] + "\n\n")
    h2("Traffic Overview")
    table(
        headers=["Metric", "Current", "Previous", "Change"],
        rows=[
            ["Organic Sessions", f"{t['organic_sessions']:,}", f"{t['organic_sessions_prev']:,}", _pct_str(t["organic_sessions_change_pct"])],
            ["Total Sessions",   f"{t['total_sessions']:,}",   f"{t['total_sessions_prev']:,}",   _pct_str(t["total_sessions_change_pct"])],
            ["New Users",        f"{t['new_users']:,}",        f"{t['new_users_prev']:,}",        _pct_str(t["new_users_change_pct"])],
        ],
    )
    h2("Monthly Organic Sessions")
    mark("traffic_organic")
    h2("Traffic by Channel")
    table(
        headers=["Channel", "Sessions", "Share"],
        rows=[
            [ch["channel"],
             f"{ch['sessions']:,}",
             f"{ch['sessions'] / max(sum(c['sessions'] for c in t['top_channels']), 1) * 100:.1f}%"]
            for ch in t["top_channels"][:6]
        ],
    )
    mark("traffic_channels")
    ins("\n")
    top_channel = t["top_channels"][0]["channel"] if t["top_channels"] else "Organic Search"
    box("KEY INSIGHTS", [
        f"Organic sessions: {t['organic_sessions']:,}  ({_pct_str(t['organic_sessions_change_pct'])} vs last month)",
        f"Total sessions across all channels: {t['total_sessions']:,}",
        f"New users this month: {t['new_users']:,}  ({_pct_str(t['new_users_change_pct'])} vs last month)",
        f"Top traffic source: {top_channel}",
    ], color="insight")
    ins("\n")

    # ── 4. Engagement Metrics ─────────────────────────────────────────────────
    h1("4. Engagement Metrics")
    h2("Engagement Overview")
    table(
        headers=["Metric", "Value", "Benchmark"],
        rows=[
            ["Bounce Rate",          f"{t['bounce_rate']}%",                      "Under 60% is strong"],
            ["Avg Session Duration", _sec_to_duration(t["avg_session_duration_sec"]), "Over 2 min is good"],
            ["New Users",            f"{t['new_users']:,}",                        "-"],
            ["Total Sessions",       f"{t['total_sessions']:,}",                   "-"],
        ],
    )
    mark("engagement")
    ins("\n")
    bounce_note = "Bounce rate is within a healthy range." if float(t["bounce_rate"]) < 60 else "Bounce rate needs improvement. Focus on page relevance."
    box("KEY INSIGHTS", [
        f"Bounce rate: {t['bounce_rate']}%  (lower is better)",
        f"Average session duration: {_sec_to_duration(t['avg_session_duration_sec'])}",
        bounce_note,
        "Session duration reflects how engaged users are with the content.",
    ], color="insight")
    ins("\n")

    # ── 5. Business Impact ────────────────────────────────────────────────────
    h1("5. Business Impact")
    h2("Goal Performance")
    org_target = targets.get("organic_sessions_goal", "-")
    kw_target  = targets.get("top_10_keywords_goal", "-")
    bl_target  = targets.get("new_backlinks_goal", "-")
    org_status = _goal_status(t["organic_sessions"], org_target)
    kw_status  = _goal_status(k["keywords_in_top_10"], kw_target)
    bl_status  = _goal_status(b["new_backlinks_count"], bl_target)
    table(
        headers=["KPI", "Target", "Actual", "Status"],
        rows=[
            ["Organic Sessions",
             f"{org_target:,}" if isinstance(org_target, int) else str(org_target),
             f"{t['organic_sessions']:,}", org_status],
            ["Keywords in Top 10", str(kw_target), str(k["keywords_in_top_10"]), kw_status],
            ["New Backlinks",      str(bl_target), str(b["new_backlinks_count"]), bl_status],
        ],
    )
    mark("goal_performance")
    ins("\n")
    box("KEY INSIGHTS", [
        f"Organic sessions: {t['organic_sessions']:,} / {org_target} target  [{org_status}]",
        f"Top 10 keywords: {k['keywords_in_top_10']} / {kw_target} target  [{kw_status}]",
        f"New backlinks: {b['new_backlinks_count']} / {bl_target} target  [{bl_status}]",
    ], color="insight")
    ins("\n")

    # ── 6. Keyword Rankings ───────────────────────────────────────────────────
    h1("6. Keyword Rankings")
    h2("Most Improved Rankings")
    improved_rows = [
        [kw["keyword"], str(round(kw["position_prev"], 1)), str(round(kw["position"], 1)), f"+{kw['delta']}"]
        for kw in k["most_improved"][:5]
    ] or [["No data available", "-", "-", "-"]]
    table(headers=["Keyword", "Prev Position", "Current Position", "Change"], rows=improved_rows)

    h2("Most Declined Rankings")
    declined_rows = [
        [kw["keyword"], str(round(kw["position_prev"], 1)), str(round(kw["position"], 1)), str(kw["delta"])]
        for kw in k["most_declined"][:5]
    ] or [["No data available", "-", "-", "-"]]
    table(headers=["Keyword", "Prev Position", "Current Position", "Change"], rows=declined_rows)
    h2("Keyword Ranking Distribution")
    mark("keyword_distribution")
    mark("keyword_rankings")
    ins("\n")
    best = k["most_improved"][0] if k["most_improved"] else None
    best_line = (
        f"Best improvement: '{best['keyword']}' moved from pos {round(best['position_prev'],1)} to {round(best['position'],1)}"
        if best else f"{k['lost_keywords_count']} keywords dropped from rankings"
    )
    box("KEY INSIGHTS", [
        f"{k['keywords_in_top_3']} keywords in top 3 positions   |   {k['keywords_in_top_10']} in top 10",
        f"{k['new_keywords_count']} new keywords entered Google rankings",
        best_line,
        f"{k['total_keywords_tracked']} total keywords tracked this month",
    ], color="insight")
    ins("\n")

    # ── 7. Backlinks ──────────────────────────────────────────────────────────
    h1("7. Backlinks")
    ins(sections["backlinks"] + "\n\n")
    h2("Backlink Summary")
    table(
        headers=["Metric", "Value"],
        rows=[
            ["Domain Rating (DR)",          str(b["domain_rating"])],
            ["Total Backlinks",             str(b["total_backlinks"])],
            ["Referring Domains",           str(b["referring_domains"])],
            ["New Backlinks (this month)",  str(b["new_backlinks_count"])],
            ["Lost Backlinks (this month)", str(b["lost_backlinks_count"])],
            ["New Dofollow Links",          str(b["dofollow_new"])],
            ["Avg DR of New Links",         str(b["avg_dr_new_backlinks"])],
        ],
    )
    mark("backlink_overview")
    ins("\n")
    box("KEY INSIGHTS", [
        f"New backlinks acquired: {b['new_backlinks_count']}  ({b['dofollow_new']} dofollow)",
        f"Lost backlinks: {b['lost_backlinks_count']}",
        f"Domain Rating: {b['domain_rating']}   |   Referring Domains: {b['referring_domains']}",
        f"Average DR of new links: {b['avg_dr_new_backlinks']}",
    ], color="insight")
    ins("\n")

    # ── 8. Content Distribution ───────────────────────────────────────────────
    blog_data   = context.get("blog_posts", {})
    blog_items  = blog_data.get("items", [])
    blog_total  = blog_data.get("total", 0)

    h1("8. Content Distribution")
    ins(
        f"Blog content published during {month_display}. "
        f"Content distribution drives organic visibility, referral traffic, "
        f"and topical authority for {domain}.\n\n"
    )
    h2("Blog Posts Published")
    ins(f"Total Blog Posts Published: {blog_total}\n\n")
    blog_table_rows = [
        [e["platform"], e["link"]] for e in blog_items
    ] or [["No blog posts recorded for this month.", "-"]]
    table(headers=["Platform", "Link"], rows=blog_table_rows)
    ins("\n")

    # ── 9. Authority Building ─────────────────────────────────────────────────
    listings_data  = context.get("business_listings", {})
    listings_items = listings_data.get("items", [])
    listings_total = listings_data.get("total", 0)

    h1("9. Authority Building")
    ins(
        f"Business directory submissions completed in {month_display}. "
        f"Each listing builds domain authority, improves local SEO signals, "
        f"and creates additional indexed backlinks for {domain}.\n\n"
    )
    h2("Business Listings / Backlinks")
    ins(f"Total Business Listings Created: {listings_total}\n\n")
    listings_table_rows = [
        [e["platform"], e["link"]] for e in listings_items
    ] or [["No business listings recorded for this month.", "-"]]
    table(headers=["Platform", "Link"], rows=listings_table_rows)
    ins("\n")

    # ── 10. Content Performance ───────────────────────────────────────────────
    h1("10. Content Performance")
    h2("Top Queries by Organic Clicks (Source: Google Search Console)")
    content_rows = [
        [
            kw["keyword"],
            f"{kw['clicks']:,}",
            f"{kw['impressions']:,}",
            f"{kw['ctr']:.2f}%",
            str(round(kw["position"], 1)),
        ]
        for kw in k["top_by_clicks"][:10]
    ] or [["No data available", "-", "-", "-", "-"]]
    table(
        headers=["Query", "Clicks", "Impressions", "CTR", "Avg Position"],
        rows=content_rows,
    )
    mark("top_pages")
    mark("ctr_keywords")
    ins("\n")

    # ── 11. Next Steps ────────────────────────────────────────────────────────
    h1("11. Next Steps")
    ins(sections["next_steps"] + "\n\n")
    box("GROWTH OPPORTUNITIES", [
        "Move top 10 keywords into top 3 positions for higher click share.",
        "Create content targeting high-impression, low-CTR keywords in GSC.",
        "Continue building high-DR backlinks to increase Domain Rating.",
        "Review and update underperforming pages to improve engagement.",
        "Monitor Core Web Vitals and page speed scores monthly.",
    ], color="growth")
    ins("\n")

    table_specs.sort(key=lambda x: x["index"], reverse=True)
    return requests, table_specs, chart_markers


# ── Table insertion and fill ──────────────────────────────────────────────────

def _insert_tables_and_fill(docs_service, doc_id: str, table_specs: list):
    if not table_specs:
        return

    insert_reqs = []
    for spec in table_specs:
        if spec.get("is_highlight"):
            rows_count = 1
            cols_count = 1
        else:
            rows_count = 1 + len(spec["rows"])
            cols_count = len(spec["headers"])
        insert_reqs.append({
            "insertTable": {
                "rows":     rows_count,
                "columns":  cols_count,
                "location": {"index": spec["index"]},
            }
        })

    docs_service.documents().batchUpdate(
        documentId=doc_id, body={"requests": insert_reqs}
    ).execute()

    # Retry the GET on transient connection errors (the doc can be large)
    doc = None
    for attempt in range(4):
        try:
            doc = docs_service.documents().get(documentId=doc_id).execute()
            break
        except Exception as exc:
            if attempt < 3:
                wait = 2 ** attempt
                log.warning("Document GET failed (attempt %d): %s — retrying in %ds", attempt + 1, exc, wait)
                time.sleep(wait)
            else:
                raise
    doc_tables = [el for el in doc["body"]["content"] if "table" in el]

    specs_in_doc_order = list(reversed(table_specs))
    if len(doc_tables) < len(specs_in_doc_order):
        log.warning("Expected %d tables but found %d.", len(specs_in_doc_order), len(doc_tables))
        specs_in_doc_order = specs_in_doc_order[:len(doc_tables)]

    all_cells  = []   # (para_start, cell_text, is_header, title_len)
    style_reqs = []   # updateTableCellStyle for highlight box backgrounds

    for table_elem, spec in zip(doc_tables, specs_in_doc_order):
        is_highlight  = spec.get("is_highlight", False)
        all_rows_data = spec["rows"] if is_highlight else [spec["headers"]] + spec["rows"]

        for row_idx, (table_row, row_data) in enumerate(
            zip(table_elem["table"]["tableRows"], all_rows_data)
        ):
            for table_cell, cell_value in zip(table_row["tableCells"], row_data):
                para_start = table_cell["content"][0]["startIndex"]
                is_header  = (not is_highlight) and (row_idx == 0)
                title_len  = spec.get("box_title_len", 0) if is_highlight else 0
                all_cells.append((para_start, str(cell_value), is_header, title_len))

        # Queue background colour for highlight boxes
        if is_highlight:
            style_reqs.append({
                "updateTableCellStyle": {
                    "tableCellStyle": {
                        "backgroundColor": {"color": {"rgbColor": spec.get("box_color", _INSIGHT_BG)}}
                    },
                    "fields": "backgroundColor",
                    "tableRange": {
                        "tableCellLocation": {
                            "tableStartLocation": {"index": table_elem["startIndex"]},
                            "rowIndex":    0,
                            "columnIndex": 0,
                        },
                        "rowSpan": 1,
                        "columnSpan": 1,
                    },
                }
            })

    # Apply background colours first (no text shift)
    if style_reqs:
        docs_service.documents().batchUpdate(
            documentId=doc_id, body={"requests": style_reqs}
        ).execute()

    all_cells.sort(key=lambda x: x[0], reverse=True)

    fill_reqs = []
    for para_start, cell_text, is_header, title_len in all_cells:
        if not cell_text:
            cell_text = "-"
        fill_reqs.append({"insertText": {"location": {"index": para_start}, "text": cell_text}})

        # Blue bold header for regular table header row
        if is_header:
            fill_reqs.append({
                "updateTextStyle": {
                    "range": {"startIndex": para_start, "endIndex": para_start + _u(cell_text)},
                    "textStyle": _HEADER_CELL_STYLE,
                    "fields": "bold,foregroundColor",
                }
            })

        # Bold blue title line for highlight boxes
        if title_len > 0:
            fill_reqs.append({
                "updateTextStyle": {
                    "range": {"startIndex": para_start, "endIndex": para_start + title_len},
                    "textStyle": _BOX_TITLE_STYLE,
                    "fields": "bold,fontSize,foregroundColor",
                }
            })

    if fill_reqs:
        docs_service.documents().batchUpdate(
            documentId=doc_id, body={"requests": fill_reqs}
        ).execute()


# ── Chart upload and insertion ────────────────────────────────────────────────

def _upload_chart(drive_service, chart_path: Path) -> str | None:
    """Upload a chart PNG to Drive, make it publicly readable, return its URI."""
    try:
        media = MediaFileUpload(str(chart_path), mimetype="image/png", resumable=False)
        file_meta = {"name": chart_path.name, "mimeType": "image/png"}
        uploaded = drive_service.files().create(
            body=file_meta, media_body=media, fields="id", supportsAllDrives=True
        ).execute()
        file_id = uploaded["id"]

        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        log.info("Chart uploaded to Drive: %s -> %s", chart_path.name, url)
        return url
    except Exception as exc:
        log.warning("Failed to upload chart %s: %s", chart_path.name, exc)
        return None


def _find_markers_in_doc(doc_content: list, marker_names: list) -> dict:
    """
    Scan doc body content for chart marker paragraphs.
    Returns {marker_name: {"start": int, "end": int, "marker_text": str}}
    where start/end are the text content indices (excluding the trailing newline).
    """
    found = {}
    for element in doc_content:
        para = element.get("paragraph")
        if not para:
            continue
        for elem in para.get("elements", []):
            tr = elem.get("textRun", {})
            content = tr.get("content", "")
            for name in marker_names:
                marker_text = f"{_CHART_PREFIX}{name}{_CHART_SUFFIX}"
                if marker_text in content:
                    start = elem["startIndex"]
                    end   = start + _u(marker_text)
                    found[name] = {"start": start, "end": end, "marker_text": marker_text}
    return found


def _insert_charts_into_doc(docs_service, drive_service, doc_id: str,
                             chart_markers: list, charts: dict):
    """
    For each chart marker in the document:
      1. Upload the chart PNG to Drive
      2. Find the marker paragraph in the live document
      3. Delete the marker text
      4. Insert the image at that position
    """
    if not chart_markers or not charts:
        return

    # Upload all charts first
    chart_urls = {}
    for name, path in charts.items():
        if path and Path(path).exists():
            url = _upload_chart(drive_service, Path(path))
            if url:
                chart_urls[name] = url

    if not chart_urls:
        log.warning("No charts were uploaded successfully — skipping image insertion.")
        return

    # Process each marker one at a time (read doc fresh each iteration to get
    # accurate indices after previous insertions/deletions shift the content)
    for marker_info in chart_markers:
        name = marker_info["name"]
        if name not in chart_urls:
            continue

        doc = docs_service.documents().get(documentId=doc_id).execute()
        markers_in_doc = _find_markers_in_doc(
            doc["body"]["content"], [name]
        )
        if name not in markers_in_doc:
            log.warning("Marker [CHART:%s] not found in document — skipping.", name)
            continue

        info = markers_in_doc[name]
        start = info["start"]
        end   = info["end"]
        url   = chart_urls[name]

        # Step 1: delete the marker text
        # Step 2: insert image at the now-empty position
        # Both are sent as one batchUpdate (delete first, then insert at same index)
        reqs = [
            {
                "deleteContentRange": {
                    "range": {"startIndex": start, "endIndex": end}
                }
            },
            {
                "insertInlineImage": {
                    "location": {"index": start},
                    "uri": url,
                    "objectSize": {
                        "width":  {"magnitude": 430, "unit": "PT"},
                        "height": {"magnitude": 242, "unit": "PT"},
                    },
                }
            },
        ]
        try:
            docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": reqs}
            ).execute()
            log.info("Inserted chart '%s' into document.", name)
        except Exception as exc:
            log.warning("Failed to insert chart '%s': %s", name, exc)


# ── Public entry point ────────────────────────────────────────────────────────

def export_to_gdocs(context: dict, sections: dict, config: dict,
                    client_id: str = "", charts: dict = None) -> str:
    """
    Creates a fully formatted Google Doc SEO report with sections, tables, and charts.
    Returns the URL of the created document.
    """
    creds = _get_credentials()
    docs_service  = build("docs",  "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    client_name = context["client"]["name"]
    short_id    = client_id if client_id else client_name
    doc_title   = _format_doc_title(short_id, context["report_month"])

    # Resolve destination folder:
    # If gdocs_folder_id is set, auto-create a "CLIENT NAME" subfolder inside it.
    # Otherwise fall back to no parent (My Drive root).
    folder_id = config["report"].get("gdocs_folder_id", "") or os.environ.get("GDOCS_FOLDER_ID", "")
    if not folder_id or folder_id == "REPLACE_WITH_YOUR_GDRIVE_FOLDER_ID":
        folder_id = None

    if folder_id:
        subfolder_name = client_name.upper()   # e.g. "SCOTLE HIGH SCHOOL"
        try:
            folder_id = _get_or_create_subfolder(drive_service, folder_id, subfolder_name)
            log.info("Using client subfolder '%s' (id=%s)", subfolder_name, folder_id)
        except Exception as exc:
            log.warning("Could not create subfolder '%s': %s — saving to parent folder.", subfolder_name, exc)

    file_meta = {"name": doc_title, "mimeType": "application/vnd.google-apps.document"}
    if folder_id:
        file_meta["parents"] = [folder_id]

    created = drive_service.files().create(
        body=file_meta, fields="id", supportsAllDrives=True
    ).execute()
    doc_id = created["id"]
    log.info("Created Google Doc: '%s'  id=%s  folder=%s", doc_title, doc_id, folder_id)

    # Write all text content with heading styles
    text_requests, table_specs, chart_markers = _build_text_requests(context, sections, short_id)
    docs_service.documents().batchUpdate(
        documentId=doc_id, body={"requests": text_requests}
    ).execute()
    log.info("Text content written (%d requests)", len(text_requests))

    # Insert and fill all data tables
    _insert_tables_and_fill(docs_service, doc_id, table_specs)
    log.info("Inserted and filled %d data tables", len(table_specs))

    # Insert charts
    if charts:
        log.info("Inserting %d charts into document...", len(charts))
        _insert_charts_into_doc(docs_service, drive_service, doc_id, chart_markers, charts)
        log.info("Chart insertion complete.")

    return f"https://docs.google.com/document/d/{doc_id}/edit"
