import logging
import os
from pathlib import Path

import requests

from immich_backup.local_disk import fetch_local_assets
from immich_backup.schemas import Settings, User, UserSync

logger = logging.getLogger(__name__)

GIGABYTE = 1024**3
AVERAGE_ASSET_BYTES = 500 * 1024  # 500KB


def get_folder_size_gb(path: Path) -> float:
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())
    return total_bytes / GIGABYTE


def trigger_syncthing_scan(configs: Settings) -> None:
    try:
        url = f"{configs.syncthing_url}/rest/db/scan?folder={configs.syncthing_folder_id}"
        requests.post(
            url,
            headers={"X-API-Key": configs.syncthing_key.get_secret_value()},
            timeout=10,
        )
        logger.info("Syncthing scan triggered.")
    except Exception as e:
        logger.warning(f"Scan trigger failed: {e}")


def run_sync_logic(configs: Settings) -> None:
    current_gb = get_folder_size_gb(configs.syncthing_dir)
    if current_gb >= configs.lower_limit_gb:
        logger.info(f"Throttled: {current_gb:.2f}GB. Waiting for space.")
        return

    remaining_bytes = (configs.upper_limit_gb - current_gb) * GIGABYTE
    users = UserSync.load(generate_default=False)
    for index, user in enumerate(users.users):
        if remaining_bytes <= 0:
            logger.info(f"Reached upper limit. Stopping sync for {user=}.")
            continue

        user_quota_bytes = remaining_bytes / (len(users.users) - index)
        added_bytes = sync_per_user(configs, user, user_quota_bytes)
        if not added_bytes:
            logger.info(f"No new assets for user {user.username}.")
            continue

        remaining_bytes -= added_bytes
        users.save()


def sync_per_user(configs: Settings, user: User, user_quota_bytes: float) -> int:
    assets = fetch_local_assets(configs.immich_library_dir, user.username, user.asset_created_after)
    added_bytes = 0
    for asset_path, asset_size, asset_created_at in sorted(assets, key=lambda a: a[2]):
        asset_relative_path = asset_path.relative_to(configs.immich_library_dir)
        dest = Path(configs.syncthing_dir) / asset_relative_path
        if dest.exists():
            logger.warning(f"Destination {dest} already exists. Skipping {asset_path}.")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        os.link(asset_path, dest)
        added_bytes += asset_size
        if added_bytes >= user_quota_bytes:
            user.asset_created_after = asset_created_at
            break

    logger.info(f"Added {added_bytes / GIGABYTE:.2f}GB of videos for user {user.username}.")
    return added_bytes
