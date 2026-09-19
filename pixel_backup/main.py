import asyncio
import logging
from datetime import datetime, timedelta

from pixel_backup.env import ENV_VARS
from pixel_backup.sync import sync_all_users
from pixel_backup.utils import seconds_until_next_cron

logger = logging.getLogger(__name__)

run_event = asyncio.Event()

POLLING_INTERVAL_SECONDS = 5


async def sync_loop() -> None:
    now = datetime.now(ENV_VARS.timezone)
    sleep_secs = seconds_until_next_cron(ENV_VARS.cron_schedule, now, ENV_VARS.min_sleep_seconds)
    next_sync_time = now + timedelta(seconds=sleep_secs)

    logger.info(f"Next sync at {next_sync_time}. Sleeping for {sleep_secs:.0f} seconds...")
    await asyncio.sleep(sleep_secs)

    await asyncio.to_thread(sync_all_users, ENV_VARS)


async def run_daemon() -> None:
    backoff_seconds = 0
    logger.info("Executing continuous sync...")
    while True:
        if not run_event.is_set():
            await asyncio.sleep(POLLING_INTERVAL_SECONDS)
            continue

        try:
            await sync_loop()
            backoff_seconds = 0
        except asyncio.CancelledError:
            logger.info("Sync loop cancelled. Shutting down.")
            raise
        except Exception:
            backoff_seconds = min(backoff_seconds * 2 or 60, 3600)
            logger.exception(f"Sync failed. Retrying in {backoff_seconds} seconds...")
            await asyncio.sleep(backoff_seconds)


if __name__ == "__main__":
    asyncio.run(run_daemon())
