import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from django_bolt.status_codes import HTTP_400_BAD_REQUEST

from pixel_backup.env import ENV_VARS

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


def send_discord_notification(message: str, discord_webhook_url: str = "") -> None:
    if ENV_VARS.pytest_version:
        logger.info("Skipped during unit tests.")
        return

    if not discord_webhook_url:
        logger.warning("Discord webhook URL is not set. Skipping notification.")
        return

    data = json.dumps({"content": message}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "pixel-backup/0.1"}
    request = Request(discord_webhook_url, data=data, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status >= HTTP_400_BAD_REQUEST:
                raise URLError(f"HTTP {response.status}")

        logger.info(f"Notification sent successfully: {message=}")
    except Exception:
        logger.exception(f"Error sending notification: {message=}")
