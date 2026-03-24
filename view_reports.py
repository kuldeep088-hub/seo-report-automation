"""
View all generated reports for all clients.
Usage: python view_reports.py
       python view_reports.py --client scotle
"""

import argparse
import json
from pathlib import Path


def show_reports(client_id: str = None):
    clients_dir = Path("clients")
    client_dirs = (
        [clients_dir / client_id]
        if client_id
        else sorted(d for d in clients_dir.iterdir() if d.is_dir() and (d / "config.yaml").exists())
    )

    for client_dir in client_dirs:
        log_path = client_dir / "reports_log.json"
        if not log_path.exists():
            print(f"\n{client_dir.name.upper()}: no reports yet.")
            continue

        entries = json.loads(log_path.read_text(encoding="utf-8"))
        print(f"\n{'=' * 60}")
        print(f"  {client_dir.name.upper()} — {len(entries)} report(s)")
        print(f"{'=' * 60}")
        for e in entries:
            print(f"  {e['month']}  |  generated: {e['generated']}")
            print(f"           {e['url']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default=None)
    args = parser.parse_args()
    show_reports(args.client)
