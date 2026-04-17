import logging
import os
import time
from pathlib import Path

from pixel_backup.local_disk import fetch_local_assets
from pixel_backup.schemas import Settings, UserConfig
from pixel_backup.utils import GIGABYTE, generate_destination_path, get_folder_size_gb, validate_source_dir

logger = logging.getLogger(__name__)

MAX_LINK_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5


def sync_all_users(configs: Settings, dry_run: bool = False):
    start_time = time.monotonic()
    current_gb = get_folder_size_gb(configs.syncthing_dir)
    if current_gb >= configs.lower_limit_gb:
        logger.info(f"Skipped. Sync folder is still full: {current_gb:.2f}GB. Waiting for space.")
        return

    remaining_bytes = (configs.upper_limit_gb - current_gb) * GIGABYTE
    users = UserConfig.load(generate_default=False)

    total_files = 0
    total_bytes = 0
    for index, user in enumerate(users.users):
        if remaining_bytes <= 0:
            logger.info(f"Reached upper limit. Stopping sync for {user=}.")
            continue

        user_quota_bytes = remaining_bytes / (len(users.users) - index)
        logger.info(f"Syncing user {user.username} with quota of {user_quota_bytes / GIGABYTE:.2f}GB...")
        try:
            added_bytes, added_files, last_timestamp_ns = sync_per_source(
                configs.syncthing_dir,
                user.username,
                user.source_dir,
                user.last_timestamp_ns,
                user_quota_bytes,
                dry_run,
            )
        except Exception:
            logger.exception(f"Failed to sync for user {user.username}. Skipping.")
            continue

        if not added_bytes:
            logger.info(f"No new assets for user {user.username}.")
            continue

        action = "Would add" if dry_run else "Added"
        logger.info(f"{action} {len(added_files)} files ({added_bytes / GIGABYTE:.2f}GB) for user {user.username}.")
        remaining_bytes -= added_bytes
        total_files += len(added_files)
        total_bytes += added_bytes

        if not dry_run:
            user.update_timestamp(last_timestamp_ns)
            users.save()

    elapsed = time.monotonic() - start_time
    logger.info(f"Sync complete: {total_files} files, {total_bytes / GIGABYTE:.2f}GB in {elapsed:.1f}s.")


def sync_per_source(
    dest_dir: Path,
    username: str,
    source_dir: Path,
    last_timestamp_ns: int,
    user_quota_bytes: float,
    dry_run: bool = False,
) -> tuple[int, list[Path], int]:
    validate_source_dir(source_dir, dest_dir)
    assets = fetch_local_assets(source_dir, last_timestamp_ns)
    if not assets:
        return 0, [], last_timestamp_ns

    added_bytes = 0
    added_files = []
    action = "Previewing" if dry_run else "Generating"
    logger.info(f"Found {len(assets)} new assets for user {username}. {action} links...")
    created_dirs = set()
    dest_user_dir = Path(dest_dir, username)
    for asset_path, asset_size, asset_created_at_ns in sorted(assets, key=lambda a: a[2]):
        dest = generate_destination_path(dest_user_dir, asset_path)
        if dest.exists():
            logger.warning(f"Skipping {asset_path=}. Destination already exists: {dest}")
            continue

        last_timestamp_ns = asset_created_at_ns
        if not dry_run:
            if dest.parent not in created_dirs:
                dest.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.add(dest.parent)

            link_with_retry(asset_path, dest)

        added_bytes += asset_size
        added_files.append(dest)
        if added_bytes >= user_quota_bytes:
            break

    return added_bytes, added_files, last_timestamp_ns


def link_with_retry(src: Path, dest: Path, retries: int = MAX_LINK_RETRIES) -> None:
    for attempt in range(1, retries + 1):
        try:
            os.link(src, dest)
            return
        except OSError:
            if attempt == retries:
                raise

            logger.warning(f"Failed to link {src} -> {dest} (attempt {attempt}/{retries}). Retrying...")
            time.sleep(RETRY_DELAY_SECONDS * attempt)
