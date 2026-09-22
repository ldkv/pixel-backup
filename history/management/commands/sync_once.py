import logging

from django.core.management.base import BaseCommand, CommandParser

from history.models import GlobalConfig
from pixel_backup.core.sync import sync_all_users

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
            logger.info("DRY RUN mode enabled. No assets will be linked.")

        global_config = GlobalConfig.objects.get()
        sync_all_users(global_config, dry_run=dry_run)
