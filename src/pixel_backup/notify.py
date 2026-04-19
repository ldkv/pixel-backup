import json
import logging
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


def send_discord_notification(message: str):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("Discord webhook URL is not set. Skipping notification.")
        return

    data = json.dumps({"content": message}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "pixel-backup/0.1"}
    request = Request(webhook_url, data=data, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status >= 400:
                raise URLError(f"HTTP {response.status}")
        logger.info(f"Notification sent successfully: {message=}")
    except Exception:
        logger.exception(f"Error sending notification: {message=}")
