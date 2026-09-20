import logging
import os
import time
from pathlib import Path

from pixel_backup.env import MEGABYTE, Settings
from pixel_backup.local_disk import fetch_local_assets
from pixel_backup.notify import send_discord_notification
from pixel_backup.schemas import UserConfig
from pixel_backup.utils import generate_destination_path, get_remaining_quota_bytes, validate_source_dir

logger = logging.getLogger(__name__)

MAX_LINK_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5


def sync_all_users(settings: Settings, dry_run: bool = False) -> None:
    start_time = time.monotonic()
    settings.syncthing_dir.mkdir(parents=True, exist_ok=True)
    remaining_bytes = get_remaining_quota_bytes(settings.syncthing_dir, settings.phone_limit_gb)
    users = UserConfig.load(path=settings.user_configs, generate_default=False)
    total_files = 0
    total_bytes = 0
    for user in users.users:
        if remaining_bytes <= settings.stop_threshold_bytes:
            message = f"Reached upper limit of {settings.phone_limit_gb}GB / {remaining_bytes=}. Please free up space on your phone."
            logger.info(message)
            if not dry_run:
                send_discord_notification(message)
            break

        logger.info(f"Syncing user {user.username} with quota of {remaining_bytes / MEGABYTE:.2f}MB...")
        try:
            added_bytes, added_files, last_timestamp_ns = sync_per_source(
                settings.syncthing_dir,
                user.username,
                user.source_dir,
                user.last_timestamp_ns,
                remaining_bytes,
                dry_run,
            )
        except Exception:
            logger.exception(f"Failed to sync for user {user.username}. Skipping.")
            continue

        if not added_bytes:
            logger.info(f"No new assets for user {user.username}.")
            continue

        action = "Would add" if dry_run else "Added"
        logger.info(f"{action} {len(added_files)} files ({added_bytes / MEGABYTE:.2f}MB) for user {user.username}.")
        remaining_bytes -= added_bytes
        total_files += len(added_files)
        total_bytes += added_bytes

        if not dry_run:
            user.update_timestamp(last_timestamp_ns)
            users.save()

    elapsed = time.monotonic() - start_time
    message = f"Sync complete: {total_files} files, {total_bytes / MEGABYTE:.2f}MB in {elapsed:.1f}s."
    logger.info(message)
    if not dry_run:
        send_discord_notification(message)


def sync_per_source(  # noqa: PLR0913, PLR0917
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
        if added_bytes + asset_size > user_quota_bytes:
            remaining_bytes = user_quota_bytes - added_bytes
            message = f"Asset size is larger than remaining quota: {asset_path=} / {asset_size=} / {remaining_bytes=}"
            logger.warning(message)
            if not dry_run:
                send_discord_notification(message)
            break

        dest = generate_destination_path(dest_user_dir, asset_path)
        if dest.exists():
            logger.warning(f"Skipping {asset_path=}. Destination already exists: {dest}")
            continue

        if not dry_run:
            if dest.parent not in created_dirs:
                dest.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.add(dest.parent)

            if not link_with_retry(asset_path, dest):
                continue

        action = "Would link" if dry_run else "Linked"
        logger.info(f"{action} {asset_path} -> {dest}")
        last_timestamp_ns = asset_created_at_ns
        added_bytes += asset_size
        added_files.append(dest)

    return added_bytes, added_files, last_timestamp_ns


def link_with_retry(src: Path, dest: Path, retries: int = MAX_LINK_RETRIES) -> bool:
    for attempt in range(1, retries + 1):
        try:
            os.link(src, dest)
            return True
        except OSError:
            logger.warning(f"Failed to link {src} -> {dest} (attempt {attempt}/{retries}). Retrying...")
            time.sleep(RETRY_DELAY_SECONDS * attempt)

    logger.error(f"Failed to link {src} -> {dest} after {attempt} attempt. Skipped.")
    return False
