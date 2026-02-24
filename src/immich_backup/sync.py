import logging
import os
from pathlib import Path

from immich_backup.local_disk import fetch_local_assets
from immich_backup.schemas import Settings, User, UserConfig
from immich_backup.utils import GIGABYTE, get_folder_size_gb

logger = logging.getLogger(__name__)


def sync_all_users(configs: Settings) -> None:
    current_gb = get_folder_size_gb(configs.syncthing_dir)
    if current_gb >= configs.lower_limit_gb:
        logger.info(f"Skipped. Sync folder is still full: {current_gb:.2f}GB. Waiting for space.")
        return

    remaining_bytes = (configs.upper_limit_gb - current_gb) * GIGABYTE
    users = UserConfig.load(generate_default=False)
    for index, user in enumerate(users.users):
        if remaining_bytes <= 0:
            logger.info(f"Reached upper limit. Stopping sync for {user=}.")
            continue

        user_quota_bytes = remaining_bytes / (len(users.users) - index)
        added_bytes, last_timestamp_ns = sync_per_user(configs, user, user_quota_bytes)
        if not added_bytes:
            logger.info(f"No new assets for user {user.username}.")
            continue

        logger.info(f"Added {added_bytes / GIGABYTE:.2f}GB of videos for user {user.username}.")
        remaining_bytes -= added_bytes
        user.update_timestamp(last_timestamp_ns)
        users.save()


def sync_per_user(configs: Settings, user: User, user_quota_bytes: float) -> tuple[int, int]:
    last_timestamp_ns = user.last_timestamp_ns
    assets = fetch_local_assets(configs.immich_library_dir, user.username, last_timestamp_ns)
    if not assets:
        return 0, last_timestamp_ns

    added_bytes = 0
    for asset_path, asset_size, asset_created_at_ns in sorted(assets, key=lambda a: a[2]):
        dest = Path(configs.syncthing_dir) / asset_path.relative_to(configs.immich_library_dir)
        if dest.exists():
            logger.warning(f"Skipping {asset_path=}. Destination already exists: {dest}")
            continue

        last_timestamp_ns = asset_created_at_ns
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.link(asset_path, dest)
        added_bytes += asset_size
        if added_bytes >= user_quota_bytes:
            break

    return added_bytes, last_timestamp_ns
