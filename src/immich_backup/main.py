import logging
import time
from datetime import datetime

from croniter import croniter

from immich_backup.schemas import Settings
from immich_backup.sync import sync_all_users

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
        now = datetime.now()
        sleep_secs = croniter(configs.cron_schedule, now).get_next(float) - now.timestamp()
        time.sleep(max(configs.min_sleep_seconds, sleep_secs))
        sync_all_users(configs)


if __name__ == "__main__":
    main()
