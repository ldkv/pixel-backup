import logging
import os
import time
from pathlib import Path

from django.db import transaction

from history.models import Batch, SyncedAsset, UserConfig
from pixel_backup.env import DB_BULK_SIZE, MEGABYTE, Settings
from pixel_backup.local_disk import fetch_local_assets
from pixel_backup.notify import send_discord_notification
from pixel_backup.utils import generate_destination_path, get_remaining_quota_bytes, validate_source_dir

logger = logging.getLogger(__name__)

MAX_LINK_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5


def sync_all_users(settings: Settings, dry_run: bool = False) -> None:
    start_time = time.monotonic()
    settings.syncthing_dir.mkdir(parents=True, exist_ok=True)
    remaining_bytes = get_remaining_quota_bytes(settings.syncthing_dir, settings.phone_limit_gb)
    users = UserConfig.load()
    total_files = 0
    total_bytes = 0
    for user in users:
        if remaining_bytes <= settings.stop_threshold_bytes:
            message = f"Reached upper limit of {settings.phone_limit_gb}GB / {remaining_bytes=}. Please free up space on your phone."
            logger.info(message)
            if not dry_run:
                send_discord_notification(message)
            break

        logger.info(f"Syncing user {user.username} with quota of {remaining_bytes / MEGABYTE:.2f}MB...")
        try:
            new_batch, new_assets = sync_per_user(settings.syncthing_dir, user, remaining_bytes, dry_run)
        except Exception:
            logger.exception(f"Failed to sync for user {user.username}. Skipping.")
            continue

        if not new_assets:
            logger.info(f"No new assets for user {user.username}.")
            continue

        if dry_run:
            action = "Would sync"
        else:
            action = "Synced"
            record_batch(new_batch, new_assets)

        logger.info(
            f"{action} {len(new_assets)} new assets ({new_batch.total_bytes / MEGABYTE:.2f}MB) for {user.username=}."
        )
        total_files += new_batch.files_count
        total_bytes += new_batch.total_bytes
        remaining_bytes -= new_batch.total_bytes

    elapsed = time.monotonic() - start_time
    message = f"Sync complete: {total_files} files, {total_bytes / MEGABYTE:.2f}MB in {elapsed:.1f}s."
    logger.info(message)
    if not dry_run:
        send_discord_notification(message)


@transaction.atomic
def record_batch(new_batch: Batch, new_assets: list[SyncedAsset]) -> None:
    new_batch.save()
    max_timestamp_ns = 0
    for new_asset in new_assets:
        new_asset.batch_id = new_batch.id
        max_timestamp_ns = max(max_timestamp_ns, new_asset.created_at_ns)

    SyncedAsset.objects.bulk_create(new_assets, batch_size=DB_BULK_SIZE)
    new_batch.user_config.update_timestamp(max_timestamp_ns)


def sync_per_user(
    dest_dir: Path,
    user: UserConfig,
    user_quota_bytes: float,
    dry_run: bool = False,
) -> tuple[Batch, list[SyncedAsset]]:
    source_dir = Path(user.source_dir)
    validate_source_dir(source_dir, dest_dir)
    new_batch = Batch(user_config=user)
    already_synced_paths = SyncedAsset.get_synced_assets(user)
    local_assets = fetch_local_assets(source_dir, user.cutoff_timestamp_ns, already_synced_paths)
    if not local_assets:
        return new_batch, []

    new_assets = []
    action = "Previewing" if dry_run else "Generating"
    logger.info(
        f"Found {len(local_assets)} new assets for user {user.username}. {action} hard links with {user_quota_bytes=}..."
    )
    created_dirs = set()
    dest_user_dir = Path(dest_dir, user.username)
    for asset_path, asset_size, asset_created_at_ns in sorted(local_assets, key=lambda a: a[2]):
        if new_batch.total_bytes + asset_size > user_quota_bytes:
            remaining_bytes = user_quota_bytes - new_batch.total_bytes
            message = f"Asset size is larger than remaining quota: {asset_path=} / {asset_size=} / {remaining_bytes=}"
            logger.warning(message)
            if not dry_run:
                send_discord_notification(message)
            break

        dest = generate_destination_path(dest_user_dir, asset_path)
        if not dry_run:
            if dest.parent not in created_dirs:
                dest.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.add(dest.parent)

            if not link_with_retry(asset_path, dest):
                continue

        action = "Would link" if dry_run else "Linked"
        logger.info(f"{action} {asset_path} -> {dest}")
        new_batch.total_bytes += asset_size
        new_batch.files_count += 1
        new_assets.append(
            SyncedAsset(
                user_config=user,
                source_path=asset_path.as_posix(),
                dest_path=dest.as_posix(),
                size_bytes=asset_size,
                created_at_ns=asset_created_at_ns,
            )
        )

    return new_batch, new_assets


def link_with_retry(src: Path, dest: Path, retries: int = MAX_LINK_RETRIES) -> bool:
    if dest.exists():
        logger.warning(f"Skipping link {src=}. Destination already exists: {dest=}")
        return True

    for attempt in range(1, retries + 1):
        try:
            os.link(src, dest)
            return True
        except OSError:
            logger.warning(f"Failed to link {src} -> {dest} (attempt {attempt}/{retries}). Retrying...")
            time.sleep(RETRY_DELAY_SECONDS * attempt)

    logger.error(f"Failed to link {src} -> {dest} after {attempt} attempt. Skipped.")
    return False
