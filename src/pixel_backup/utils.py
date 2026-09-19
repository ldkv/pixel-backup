import hashlib
from datetime import datetime
from pathlib import Path

from croniter import croniter

MEGABYTE = 1024**2
GIGABYTE = MEGABYTE * 1024


def seconds_until_next_cron(cron_schedule: str, current_time: datetime, min_sleep_seconds: int) -> float:
    sleep_secs = croniter(cron_schedule, current_time).get_next(float) - current_time.timestamp()
    return max(sleep_secs, min_sleep_seconds)


def validate_source_dir(source_dir: Path, dest_dir: Path):
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist or is not a directory: {source_dir}")

    if source_dir.stat().st_dev != dest_dir.stat().st_dev:
        raise ValueError(
            f"Source directory ({source_dir}) and destination directory ({dest_dir}) "
            "must be on the same filesystem to support hard linking."
        )


def get_folder_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())


def consistent_dir(path: Path) -> str:
    path_hash = hashlib.md5(path.resolve().as_posix().encode()).hexdigest()
    return f"{path.name[:15]}_{path_hash}"


def generate_destination_path(dest_dir: Path, asset_path: Path) -> Path:
    consistent_asset_dir = consistent_dir(asset_path.parent)
    return Path(dest_dir, consistent_asset_dir, asset_path.name)
