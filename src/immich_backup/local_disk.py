import logging
import os
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


def fetch_local_assets(immich_library_dir: Path, user: str, last_timestamp_ns: int) -> list[tuple[Path, int, int]]:
    user_path = immich_library_dir / user
    if not user_path.is_dir():
        logger.error(f"{user_path=} does not exist or is not a directory.")
        return []

    logger.info(f"Fetching assets for {user=} created after {last_timestamp_ns}...")
    found_assets = []
    stack = [user_path.as_posix()]
    while stack:
        current_dir = stack.pop()
        with os.scandir(current_dir) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                    continue

                info = entry.stat()
                if info.st_mtime_ns >= last_timestamp_ns and is_media_file(entry.name):
                    found_assets.append((Path(entry.path), info.st_size, info.st_mtime_ns))

    return found_assets


def is_media_file(filename: str) -> bool:
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return True

    suffix = filename[dot_idx:].lower()
    return suffix not in IGNORED_EXTENSIONS
