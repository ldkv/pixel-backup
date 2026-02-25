import logging
import time
from datetime import datetime, timedelta

from pixel_backup.schemas import Settings
from pixel_backup.sync import sync_all_users
from pixel_backup.utils import seconds_until_next_cron

logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    configure_logging()
    while True:
        configs = Settings.load(generate_default=True)
        now = datetime.now(configs.timezone)
        sleep_secs = seconds_until_next_cron(configs.cron_schedule, now, configs.min_sleep_seconds)
        next_sync_time = now + timedelta(seconds=sleep_secs)

        logger.info(f"Next sync at {next_sync_time}. Sleeping for {sleep_secs:.0f} seconds...")
        time.sleep(sleep_secs)

        sync_all_users(configs)


if __name__ == "__main__":
    main()
