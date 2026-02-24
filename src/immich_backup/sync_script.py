import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from immich_backup.local_disk import fetch_local_assets
from immich_backup.schemas import Settings, User, UserConfig

logger = logging.getLogger(__name__)

GIGABYTE = 1024**3
AVERAGE_ASSET_BYTES = 500 * 1024  # 500KB


def get_folder_size_gb(path: Path) -> float:
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())
    return total_bytes / GIGABYTE


def run_sync_logic(configs: Settings) -> None:
    current_gb = get_folder_size_gb(configs.syncthing_dir)
    if current_gb >= configs.lower_limit_gb:
        logger.info(f"Throttled: {current_gb:.2f}GB. Waiting for space.")
        return

    remaining_bytes = (configs.upper_limit_gb - current_gb) * GIGABYTE
    users = UserConfig.load(generate_default=False)
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
    last_asset_created_at = user.asset_created_after.timestamp()
    assets = fetch_local_assets(configs.immich_library_dir, user.username, last_asset_created_at)
    if not assets:
        return 0

    added_bytes = 0
    for asset_path, asset_size, asset_created_at in sorted(assets, key=lambda a: a[2]):
        dest = Path(configs.syncthing_dir) / asset_path.relative_to(configs.immich_library_dir)
        if dest.exists():
            logger.warning(f"Destination {dest} already exists. Skipping {asset_path}.")
            continue

        last_asset_created_at = asset_created_at
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.link(asset_path, dest)
        added_bytes += asset_size
        if added_bytes >= user_quota_bytes:
            break

    user.asset_created_after = datetime.fromtimestamp(last_asset_created_at, tz=UTC)
    logger.info(f"Added {added_bytes / GIGABYTE:.2f}GB of videos for user {user.username}.")
    return added_bytes
