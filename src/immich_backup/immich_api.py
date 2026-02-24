import logging
from datetime import datetime

import requests

from immich_backup.schemas import ImmichAsset

logger = logging.getLogger(__name__)

# Ditched the idea of fetching assets in batches. Use local disk instead without immich

def fetch_immich_assets(
    immich_url: str,
    immich_api_key: str,
    created_after: datetime,
    timeout: int,
) -> list[ImmichAsset]:
    try:
        resp = requests.post(
            f"{immich_url}/api/search/metadata",
            headers={"x-api-key": immich_api_key},
            json={"createdAfter": created_after.isoformat(), "order": "asc", "size": 1000},
            timeout=timeout,
        )
        resp.raise_for_status()
        assets_data = resp.json().get("assets", {}).get("items", [])
        return sorted([ImmichAsset(**asset) for asset in assets_data], key=lambda x: x.id)
    except Exception as e:
        logger.error(f"Failed to fetch assets: {e}")
        return []


def tag_assets(
    immich_url: str,
    immich_api_key: str,
    asset_ids: list[str],
    tag: str,
    timeout: int,
) -> None:
    try:
        resp = requests.put(
            f"{immich_url}/api/tags/assets",
            headers={"x-api-key": immich_api_key},
            json={"assetIds": asset_ids, "tag": tag},
            timeout=timeout,
        )
        resp.raise_for_status()
        tagged_count = resp.json().get("count", 0)
        logger.info(f"Tagged {tagged_count} assets with {tag=}.")
    except Exception as e:
        logger.error(f"Failed to tag assets: {e}")
