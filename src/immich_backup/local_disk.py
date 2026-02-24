import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORED_EXTENSIONS = {
    ".xmp",
    ".immich",
    ".json",
    ".yaml",
    ".yml",
    ".trashed",
    ".db",
    ".ini",
    ".log",
    ".tmp",
}


def fetch_local_assets(immich_libarry_dir: Path, owner: str, created_after: datetime) -> list[tuple[Path, float, int]]:
    user_path = immich_libarry_dir / owner
    if not user_path.is_dir():
        logger.warning(f"{user_path=} does not exist or is not a directory.")
        return []

    found_assets = []
    created_after_timestamp = created_after.timestamp()
    for file in user_path.rglob("*"):
        if is_media_file(file) and (created_at := file.stat().st_mtime >= created_after_timestamp):
            found_assets.append((file, file.stat().st_size, created_at))

    return found_assets


def is_media_file(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() not in IGNORED_EXTENSIONS
