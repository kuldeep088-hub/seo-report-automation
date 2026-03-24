"""
SEO Report Automation — Entry Point
Usage: python main.py --client scotle [--month 2025-03]
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "automation.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── Config loader ────────────────────────────────────────────────────────────
def load_client_config(client_id: str) -> dict:
    config_path = Path("clients") / client_id / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found for client '{client_id}' at {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_work_log(client_id: str) -> str:
    work_log_path = Path("clients") / client_id / "work_log.md"
    if not work_log_path.exists():
        log.warning("No work_log.md found for client '%s'. Continuing without it.", client_id)
        return ""
    return work_log_path.read_text(encoding="utf-8")


# ── Pipeline ─────────────────────────────────────────────────────────────────
def run_pipeline(client_id: str, month: str, demo: bool = False):
    log.info("=" * 60)
    log.info("Starting SEO report pipeline for client: %s  month: %s", client_id, month)
    log.info("=" * 60)

    # 1. Load config & work log
    config = load_client_config(client_id)
    work_log = load_work_log(client_id)
    config["report_month"] = month
    log.info("Loaded config for '%s'", config["client"]["name"])

    # 2. Collect data
    log.info("-- Phase 2: Collecting data --")
    from collectors.google_analytics import collect_traffic
    from collectors.search_console import collect_keywords
    from collectors.search_console_pages import collect_landing_pages
    from collectors.ahrefs import collect_backlinks
    from collectors.pagespeed import collect_pagespeed

    traffic_raw   = collect_traffic(config, month)
    keywords_raw  = collect_keywords(config, month)
    pages_raw     = collect_landing_pages(config, month)
    backlinks_raw = collect_backlinks(config, month)
    pagespeed_raw = collect_pagespeed(config, month)

    from collectors.gsc_screenshot import collect_gsc_screenshot
    gsc_screenshot_path = collect_gsc_screenshot(config, month)

    from collectors.sheets_collector import collect_blog_posts, collect_business_listings, collect_backlinks_from_sheets
    blog_data      = collect_blog_posts(config, month)
    listings_data  = collect_business_listings(config, month)
    backlinks_sheet_data = collect_backlinks_from_sheets(config, month)

    # 3. Process data
    log.info("-- Phase 3: Processing data --")
    from processors.traffic import process_traffic
    from processors.keywords import process_keywords
    from processors.backlinks import process_backlinks

    traffic_data   = process_traffic(traffic_raw)
    keywords_data  = process_keywords(keywords_raw)
    backlinks_data = process_backlinks(backlinks_raw)

    # 4. Assemble context payload for AI
    context = {
        "client":             config["client"],
        "report_month":       month,
        "targets":            config["targets"],
        "traffic":            traffic_data,
        "keywords":           keywords_data,
        "backlinks":          backlinks_data,
        "landing_pages":      pages_raw,
        "pagespeed":          pagespeed_raw,
        "blog_posts":         blog_data,
        "business_listings":  listings_data,
        "backlinks_sheet":    backlinks_sheet_data,
        "work_log":           work_log,
        "gsc_screenshot":     gsc_screenshot_path,
    }

    # 5. Generate AI report
    log.info("-- Phase 4: Generating AI report --")
    from ai.report_writer import generate_report
    report_sections = generate_report(context, demo=demo)

    # 6. Generate charts
    log.info("-- Phase 5: Generating charts --")
    from charts.chart_generator import generate_all_charts
    charts = generate_all_charts(context, client_id)

    # 7. Export
    log.info("-- Phase 6: Exporting report --")
    output_formats = config["report"].get("output_format", ["pdf"])
    report_paths = []

    if "pdf" in output_formats:
        from exporters.pdf_exporter import export_pdf
        pdf_path = export_pdf(context, report_sections, client_id, month, charts=charts)
        report_paths.append(pdf_path)
        log.info("PDF saved: %s", pdf_path)

    if "gdocs" in output_formats:
        from exporters.gdocs_exporter import export_to_gdocs
        doc_url = export_to_gdocs(context, report_sections, config, client_id, charts=charts)
        log.info("Google Doc created: %s", doc_url)
        report_paths.append(doc_url)

    log.info("=" * 60)
    log.info("Report pipeline complete for %s", client_id)
    log.info("=" * 60)

    gdoc_url = None
    for path in report_paths:
        if str(path).startswith("https://"):
            log.info("GOOGLE DOC LINK: %s", path)
            gdoc_url = str(path)

    # 8. Send email
    if config["report"].get("send_email", False) and gdoc_url:
        log.info("-- Phase 7: Sending report email --")
        from exporters.email_sender import send_report_email
        send_report_email(config, gdoc_url, month)

    return report_paths


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEO Report Automation")
    parser.add_argument("--client", required=True, help="Client folder name, e.g. scotle")
    parser.add_argument(
        "--month",
        default=datetime.now().strftime("%Y-%m"),
        help="Report month in YYYY-MM format (default: current month)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Skip Claude API and use placeholder text (no credits needed)",
    )
    args = parser.parse_args()

    try:
        run_pipeline(args.client, args.month, demo=args.demo)
    except Exception as e:
        log.error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)
