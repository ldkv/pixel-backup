from pathlib import Path
from typing import NamedTuple

from django.db import transaction
from django.db.models import Max

from pixel_backup.history.models import Batch, SyncedFile
from pixel_backup.schemas import UserStateConfig


class PendingFile(NamedTuple):
    source_path: Path
    dest_path: Path
    size_bytes: int
    asset_created_at_ns: int


def is_synced(username: str, source_path: str) -> bool:
    return SyncedFile.objects.filter(username=username, source_path=source_path).exists()


def get_last_synced_ns(username: str) -> int:
    value = SyncedFile.objects.filter(username=username).aggregate(max_ns=Max("asset_created_at_ns"))["max_ns"]
    return value or 0


@transaction.atomic
def record_batch(username: str, synced_files: list[PendingFile]) -> None:
    total_bytes = sum(f.size_bytes for f in synced_files)
    batch = Batch.objects.create(username=username, files_count=len(synced_files), total_bytes=total_bytes)
    SyncedFile.objects.bulk_create(
        SyncedFile(
            batch=batch,
            username=username,
            source_path=f.source_path.as_posix(),
            dest_path=f.dest_path.as_posix(),
            size_bytes=f.size_bytes,
            asset_created_at_ns=f.asset_created_at_ns,
        )
        for f in synced_files
    )


def migrate_legacy_cursor(legacy_path: Path) -> None:
    """One-time bootstrap of the sync cursor from the old users_state.json. Idempotent via
    bulk_create(ignore_conflicts=True) + the (username, source_path) unique constraint, so
    it's safe to call on every startup."""
    if not legacy_path.exists():
        return

    state = UserStateConfig.load(path=legacy_path, generate_default=False)
    SyncedFile.objects.bulk_create(
        (
            SyncedFile(
                username=username,
                source_path=f"__migrated_cursor__:{username}",
                dest_path="",
                size_bytes=0,
                asset_created_at_ns=last_ns,
            )
            for username, last_ns in state.state.items()
        ),
        ignore_conflicts=True,
    )
