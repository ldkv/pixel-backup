import logging
import os
from datetime import datetime
from pathlib import Path

import requests

from immich_backup.schemas import ImmichAsset, Settings, User, UserSync

logger = logging.getLogger(__name__)

GIGABYTE = 1024**3


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


def fetch_immich_assets(
    immich_url: str,
    immich_api_key: str,
    created_after: datetime,
    timeout: int,
) -> list[ImmichAsset]:
    try:
        resp = requests.post(
            f"{immich_url}/search/metadata",
            headers={"x-api-key": immich_api_key},
            json={"createdAfter": created_after.isoformat()},
            timeout=timeout,
        )
        resp.raise_for_status()
        assets_data = resp.json().get("assets", {}).get("items", [])
        return sorted([ImmichAsset(**asset) for asset in assets_data], key=lambda x: x.id)
    except Exception as e:
        logger.error(f"Failed to fetch assets: {e}")
        return []


def run_sync_logic(configs: Settings) -> None:
    current_gb = get_folder_size_gb(configs.sync_dir)
    if current_gb >= configs.lower_limit_gb:
        logger.info(f"Throttled: {current_gb:.2f}GB. Waiting for space.")
        return

    remaining_bytes = (configs.upper_limit_gb - current_gb) * GIGABYTE
    users = UserSync.load(generate_default=False)
    for index, user in enumerate(users.users):
        user_quota_bytes = remaining_bytes / (len(users.users) - index)
        added_bytes = sync_per_user(configs, user, user_quota_bytes)
        if not added_bytes:
            logger.info(f"No more assets to sync for user {user.username}.")
            continue

        remaining_bytes -= added_bytes
        users.save()


def sync_per_user(configs: Settings, user: User, user_quota_bytes: float) -> int:
    assets = fetch_immich_assets(
        configs.immich_url,
        user.immich_api_key,
        user.asset_created_after,
        configs.immich_timeout_seconds,
    )
    if not assets:
        logger.info(f"No new assets for user {user.username}.")
        return 0

    added_bytes = 0
    for asset in assets:
        if asset.id <= user.last_asset_id:
            continue

        src = Path(asset.originalPath)
        dest = Path(configs.sync_dir) / src.name
        if dest.exists():
            logger.warning(f"Destination {dest} already exists. Skipping {src}.")
            continue

        if src.exists() and src.stat().st_dev == configs.sync_dir.stat().st_dev:
            os.link(src, dest)
            added_bytes += src.stat().st_size
            if added_bytes >= user_quota_bytes:
                break

    user.last_asset_id = assets[-1].id
    logger.info(f"Added {added_bytes / GIGABYTE:.2f}GB of videos for user {user.username}.")

    return added_bytes
