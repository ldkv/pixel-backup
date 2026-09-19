import logging

from django.core.management.base import BaseCommand, CommandParser

from pixel_backup.env import ENV_VARS
from pixel_backup.sync import sync_all_users

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a single backup sync for all users."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview sync without creating hard links.",
        )

    def handle(self, *args: object, **options: object) -> None:
        dry_run = bool(options["dry_run"])
        if dry_run:
            logger.info("DRY RUN mode enabled. No files will be linked.")

        sync_all_users(ENV_VARS, dry_run=dry_run)
