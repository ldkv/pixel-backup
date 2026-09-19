import argparse
import asyncio
import contextlib
import logging
import os
import signal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pixel_backup.settings")
import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

from pixel_backup.daemon import run_daemon  # noqa: E402
from pixel_backup.env import ENV_VARS  # noqa: E402
from pixel_backup.sync import sync_all_users  # noqa: E402

logger = logging.getLogger(__name__)


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


async def _run_standalone_daemon():
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, task.cancel)

    with contextlib.suppress(asyncio.CancelledError):
        await run_daemon()


def main():
    configure_logging()
    call_command("migrate", verbosity=0)
    args = parse_args()
    if args.dry_run:
        logger.info("DRY RUN mode enabled. No files will be linked.")

    if not args.permanent:
        logger.info("Executing single sync...")
        sync_all_users(ENV_VARS, dry_run=args.dry_run)
        return

    asyncio.run(_run_standalone_daemon())
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
