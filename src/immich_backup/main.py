import logging
import time

from immich_backup.syncthing import setup_syncthing

logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    configure_logging()
    setup_syncthing()
    while True:
        # Temporary
        time.sleep(6)
        continue


if __name__ == "__main__":
    main()
