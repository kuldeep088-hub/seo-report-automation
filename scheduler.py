"""
SEO Report Scheduler
Automatically generates reports for all configured clients on the 1st of every
month at 09:00, covering the previous calendar month.

Usage:
  python scheduler.py           # Start the scheduler (keeps running)
  python scheduler.py --now     # Run all clients immediately (for testing)
  python scheduler.py --client scotle  # Run a single client immediately
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_SHARED_FORMATTER = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")


def _setup_logging(run_tag: str) -> logging.FileHandler:
    """
    Attach a per-run file handler to the root logger.
    Returns the handler so it can be removed after the run.
    """
    log_path = LOG_DIR / f"run_{run_tag}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(_SHARED_FORMATTER)
    logging.getLogger().addHandler(fh)
    return fh, log_path


def _teardown_logging(fh: logging.FileHandler):
    logging.getLogger().removeHandler(fh)
    fh.close()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "automation.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def prev_month() -> str:
    """Return the previous calendar month as YYYY-MM.
    If today is any day in March → returns '2025-02'.
    """
    first_of_current = datetime.now().replace(day=1)
    last_day_prev    = first_of_current - timedelta(days=1)
    return last_day_prev.strftime("%Y-%m")


def discover_clients() -> list:
    """Return all client IDs that have a config.yaml, excluding example_client."""
    clients_dir = Path("clients")
    return [
        folder.name
        for folder in sorted(clients_dir.iterdir())
        if folder.is_dir()
        and (folder / "config.yaml").exists()
        and folder.name != "example_client"
    ]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all_clients(month: str = None, single_client: str = None):
    """
    Run the full pipeline for all (or one) client(s).
    `month` defaults to the previous calendar month.
    """
    from main import run_pipeline

    if month is None:
        month = prev_month()

    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh, log_path = _setup_logging(run_tag)

    clients = [single_client] if single_client else discover_clients()

    if not clients:
        log.warning("No clients found in clients/ folder.")
        _teardown_logging(fh)
        return

    month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    log.info("=" * 65)
    log.info("SCHEDULED RUN  |  Report month: %s  |  Clients: %s",
             month_label, ", ".join(clients))
    log.info("Per-run log: %s", log_path)
    log.info("=" * 65)

    results = {}
    for client_id in clients:
        log.info(">>> Starting pipeline for client: %s", client_id)
        try:
            paths = run_pipeline(client_id, month)
            results[client_id] = {"status": "OK", "outputs": paths}
            log.info(">>> Completed: %s", client_id)
        except Exception as exc:
            results[client_id] = {"status": "FAILED", "error": str(exc)}
            log.error(">>> FAILED: %s — %s", client_id, exc, exc_info=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=" * 65)
    log.info("RUN SUMMARY  |  %s", month_label)
    ok_count   = sum(1 for r in results.values() if r["status"] == "OK")
    fail_count = sum(1 for r in results.values() if r["status"] == "FAILED")
    log.info("  Total clients : %d", len(clients))
    log.info("  Succeeded     : %d", ok_count)
    log.info("  Failed        : %d", fail_count)
    for client_id, result in results.items():
        if result["status"] == "OK":
            for path in result.get("outputs", []):
                if str(path).startswith("https://"):
                    log.info("  [OK]  %-20s  %s", client_id, path)
        else:
            log.error("  [FAIL] %-20s  %s", client_id, result["error"])
    log.info("=" * 65)

    _teardown_logging(fh)
    return results


# ── Monthly check (called daily at 09:00) ────────────────────────────────────

def _monthly_check():
    """Fires daily at 09:00; actually runs only on the 1st of the month."""
    today = datetime.now()
    if today.day == 1:
        log.info("Monthly trigger fired on %s.", today.strftime("%Y-%m-%d"))
        run_all_clients()
    else:
        log.debug("Daily check on %s — not the 1st, skipping.", today.strftime("%Y-%m-%d"))


# ── Scheduler loop ────────────────────────────────────────────────────────────

def start_scheduler():
    log.info("Scheduler started.")
    log.info("Reports will run automatically on the 1st of each month at 09:00.")
    log.info("Covering the previous calendar month (e.g. run on 1 March → report for February).")
    log.info("Press Ctrl+C to stop.")

    schedule.every().day.at("09:00").do(_monthly_check)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)   # check every 30 seconds for responsiveness
    except KeyboardInterrupt:
        log.info("Scheduler stopped by user.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEO Report Scheduler")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run all clients immediately for the previous month",
    )
    parser.add_argument(
        "--client",
        default=None,
        help="Run a single client immediately (e.g. --client scotle)",
    )
    parser.add_argument(
        "--month",
        default=None,
        help="Override report month YYYY-MM (default: previous month)",
    )
    args = parser.parse_args()

    if args.now or args.client:
        month = args.month or prev_month()
        log.info("Manual trigger — month: %s", month)
        run_all_clients(month=month, single_client=args.client)
    else:
        start_scheduler()
