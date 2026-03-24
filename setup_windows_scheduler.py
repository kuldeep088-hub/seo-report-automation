"""
One-time setup: registers the SEO report scheduler as a Windows Task
that starts automatically at login — no manual action needed every month.

Run ONCE (as Administrator):
    python setup_windows_scheduler.py

What it does:
  - Creates a Windows Task named "SEO Report Scheduler"
  - Runs start_scheduler.bat at every Windows login
  - The scheduler then fires the report pipeline on the 1st of each month at 09:00
"""

import subprocess
import sys
from pathlib import Path

TASK_NAME   = "SEO Report Scheduler"
BAT_FILE    = str(Path(__file__).parent / "start_scheduler.bat")
PYTHON_PATH = sys.executable


def task_exists(name: str) -> bool:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", name],
        capture_output=True, text=True
    )
    return result.returncode == 0


def create_task():
    print(f"Registering Windows Task: '{TASK_NAME}'")
    result = subprocess.run([
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{BAT_FILE}"',
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/F",   # overwrite if exists
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Task created successfully.")
        print(f"The scheduler will now start automatically at every Windows login.")
        print(f"It will run the SEO report on the 1st of every month at 09:00.")
    else:
        print(f"Error creating task:")
        print(result.stderr)
        print()
        print("Try running this script as Administrator:")
        print("  Right-click Command Prompt → Run as administrator")
        print(f"  python setup_windows_scheduler.py")


def delete_task():
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                   capture_output=True)
    print(f"Task '{TASK_NAME}' removed.")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        delete_task()
    else:
        if task_exists(TASK_NAME):
            print(f"Task '{TASK_NAME}' already exists — updating it.")
        create_task()
        print()
        print("To start the scheduler now without rebooting, run:")
        print("  python scheduler.py")
        print()
        print("To remove the task later:")
        print("  python setup_windows_scheduler.py --remove")
