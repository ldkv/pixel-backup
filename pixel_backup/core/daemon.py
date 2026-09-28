import asyncio
import logging
from datetime import datetime, timedelta

from history.models import GlobalConfig
from pixel_backup.core.sync import resync_batch, sync_all_users
from pixel_backup.core.utils import seconds_until_next_cron

logger = logging.getLogger(__name__)

stop_event = asyncio.Event()
sync_lock = asyncio.Lock()

POLLING_INTERVAL_SECONDS = 5


async def trigger_manual_sync(dry_run: bool = False) -> bool:
    """Kicks off a sync in the background. Returns False without starting anything if one is already running."""
    if sync_lock.locked():
        return False

    async def _run() -> None:
        async with sync_lock:
            global_config = await GlobalConfig.load()
            await asyncio.to_thread(sync_all_users, global_config, dry_run)

    asyncio.create_task(_run())
    return True


async def trigger_manual_resync(batch_id: int, dry_run: bool = False) -> bool:
    """Kicks off a batch resync in the background. Returns False without starting anything if a sync is running."""
    if sync_lock.locked():
        return False

    async def _run() -> None:
        async with sync_lock:
            global_config = await GlobalConfig.load()
            await asyncio.to_thread(resync_batch, global_config, batch_id, dry_run)

    asyncio.create_task(_run())
    return True


async def sync_loop() -> None:
    global_config = await GlobalConfig.load()
    now = datetime.now(global_config.timezone)
    sleep_secs = seconds_until_next_cron(global_config.cron_schedule, now, global_config.min_sleep_seconds)
    next_sync_time = now + timedelta(seconds=sleep_secs)

    logger.info(f"Next sync at {next_sync_time}. Sleeping for {sleep_secs:.0f} seconds...")
    await asyncio.sleep(sleep_secs)

    async with sync_lock:
        await asyncio.to_thread(sync_all_users, global_config)


async def run_daemon() -> None:
    """Continuously sync on the configured cron schedule until cancelled."""

    backoff_seconds = 0
    logger.info("Executing continuous sync...")
    while True:
        if stop_event.is_set():
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
