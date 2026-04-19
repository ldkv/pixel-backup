import logging
from datetime import datetime

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ImmichAsset(BaseModel):
    id: str
    originalPath: str


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
            json={"createdAfter": created_after.isoformat(), "order": "desc", "size": 1000, "page": 70},
            timeout=timeout,
        )
        resp.raise_for_status()
        print(resp.json())
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


assets = fetch_immich_assets("<IMMICH_URL>", "<IMMICH_API_KEY>", datetime(2000, 4, 12), timeout=10)

print(f"Fetched {len(assets)} assets.")
