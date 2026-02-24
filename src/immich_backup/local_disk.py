import logging
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


def fetch_local_assets(immich_library_dir: Path, owner: str, last_timestamp_ns: int) -> list[tuple[Path, int, int]]:
    user_path = immich_library_dir / owner
    if not user_path.is_dir():
        logger.error(f"{user_path=} does not exist or is not a directory.")
        return []

    found_assets = []
    for file in user_path.rglob("*"):
        if is_media_file(file) and (created_at_ns := file.stat().st_mtime_ns) >= last_timestamp_ns:
            found_assets.append((file, file.stat().st_size, created_at_ns))

    return found_assets


def is_media_file(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() not in IGNORED_EXTENSIONS
