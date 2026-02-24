from datetime import datetime
from pathlib import Path

from croniter import croniter

GIGABYTE = 1024**3


def seconds_until_next_cron(cron_schedule: str, current_time: datetime, min_sleep_seconds: int) -> float:
    sleep_secs = croniter(cron_schedule, current_time).get_next(float) - current_time.timestamp()
    sleep_secs = max(sleep_secs, min_sleep_seconds)
    return sleep_secs


def get_folder_size_gb(path: Path) -> float:
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())
    return total_bytes / GIGABYTE
