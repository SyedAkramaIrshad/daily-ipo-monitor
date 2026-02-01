"""
Runs the IPO monitor every day at 9:00 AM Dubai time (UTC+4).
Keep this script running (e.g. in background or as a service).
"""

import time
from datetime import datetime, timezone, timedelta

from ipo_monitor import run_once

DUBAI_TZ = timedelta(hours=4)  # Dubai = UTC+4
TARGET_HOUR, TARGET_MINUTE = 9, 0  # 9:00 AM Dubai


def now_dubai() -> datetime:
    """Current date/time in Dubai (naive, for hour/minute comparison)."""
    utc = datetime.now(timezone.utc)
    dubai = utc + DUBAI_TZ
    return dubai.replace(tzinfo=None)


def job() -> None:
    """Run the IPO monitor once."""
    print(f"[{datetime.now().isoformat()}] Running IPO monitor...")
    try:
        run_once()
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    last_run_date = None
    print("IPO Monitor scheduler started. Runs daily at 9:00 AM Dubai time.")
    print("Press Ctrl+C to stop.")
    while True:
        now = now_dubai()
        if now.hour == TARGET_HOUR and now.minute == TARGET_MINUTE:
            if last_run_date != now.date():
                job()
                last_run_date = now.date()
        time.sleep(60)  # check every minute
