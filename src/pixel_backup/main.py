import argparse
import logging
import signal
from datetime import datetime, timedelta
from threading import Event

from pixel_backup.schemas import Settings
from pixel_backup.sync import sync_all_users
from pixel_backup.utils import seconds_until_next_cron

logger = logging.getLogger(__name__)

shutdown_event = Event()


def handle_signal(signum: int, _frame: object):
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name}. Shutting down gracefully...")
    shutdown_event.set()


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup local library to Google Pixel via Syncthing.")
    parser.add_argument(
        "--permanent",
        action="store_true",
        help="Run continuously on the cron schedule instead of a single sync.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview sync without creating hard links. Forces single-run mode.",
    )
    args = parser.parse_args()
    if args.dry_run:
        args.permanent = False

    logger.info(f"Starting with args: {args}")
    return args


def sync_loop():
    configs = Settings.load(generate_default=True)
    now = datetime.now(configs.timezone)
    sleep_secs = seconds_until_next_cron(configs.cron_schedule, now, configs.min_sleep_seconds)
    next_sync_time = now + timedelta(seconds=sleep_secs)

    logger.info(f"Next sync at {next_sync_time}. Sleeping for {sleep_secs:.0f} seconds...")
    if shutdown_event.wait(timeout=sleep_secs):
        return

    sync_all_users(configs)


def main():
    configure_logging()
    args = parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode enabled. No files will be linked.")

    if not args.permanent:
        logger.info("Executing single sync...")
        configs = Settings.load(generate_default=True)
        sync_all_users(configs, dry_run=args.dry_run)
        return

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    backoff_seconds = 0
    logger.info("Executing continuous sync...")
    while not shutdown_event.is_set():
        try:
            sync_loop()
            backoff_seconds = 0
        except Exception:
            backoff_seconds = min(backoff_seconds * 2 or 60, 3600)
            logger.exception(f"Sync failed. Retrying in {backoff_seconds} seconds...")
            if shutdown_event.wait(timeout=backoff_seconds):
                break

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
