from pathlib import Path

import pytest

from pixel_backup.history.models import Batch, SyncedFile
from pixel_backup.history.repository import (
    PendingFile,
    get_last_synced_ns,
    is_synced,
    migrate_legacy_cursor,
    record_batch,
)
from pixel_backup.schemas import UserStateConfig

pytestmark = pytest.mark.django_db


class TestIsSynced:
    def test_false_when_absent(self):
        assert is_synced("alice", "/library/alice/photo.jpg") is False

    def test_true_after_record_batch(self):
        record_batch(
            "alice",
            [PendingFile(Path("/library/alice/photo.jpg"), Path("/dest/photo.jpg"), 100, 1_000)],
        )
        assert is_synced("alice", "/library/alice/photo.jpg") is True
        assert is_synced("bob", "/library/alice/photo.jpg") is False


class TestGetLastSyncedNs:
    def test_zero_when_empty(self):
        assert get_last_synced_ns("alice") == 0

    def test_returns_max(self):
        record_batch(
            "alice",
            [
                PendingFile(Path("/library/alice/a.jpg"), Path("/dest/a.jpg"), 100, 1_000),
                PendingFile(Path("/library/alice/b.jpg"), Path("/dest/b.jpg"), 100, 5_000),
            ],
        )
        assert get_last_synced_ns("alice") == 5_000


class TestRecordBatch:
    def test_writes_batch_and_files(self):
        files = [
            PendingFile(Path("/library/alice/a.jpg"), Path("/dest/a.jpg"), 100, 1_000),
            PendingFile(Path("/library/alice/b.jpg"), Path("/dest/b.jpg"), 200, 2_000),
        ]
        record_batch("alice", files)

        batches = list(Batch.objects.values_list("username", "files_count", "total_bytes"))
        assert batches == [("alice", 2, 300)]

        rows = list(SyncedFile.objects.order_by("source_path").values_list("source_path", "batch_id"))
        assert [r[0] for r in rows] == ["/library/alice/a.jpg", "/library/alice/b.jpg"]
        assert rows[0][1] == rows[1][1]


class TestMigrateLegacyCursor:
    def test_noop_when_legacy_file_missing(self, tmp_path: Path):
        migrate_legacy_cursor(tmp_path / "missing.json")
        assert get_last_synced_ns("alice") == 0

    def test_seeds_cursor_from_legacy_state(self, tmp_path: Path):
        legacy_path = tmp_path / "users_state.json"
        UserStateConfig(state={"alice": 42_000, "bob": 7_000}).save(legacy_path)

        migrate_legacy_cursor(legacy_path)

        assert get_last_synced_ns("alice") == 42_000
        assert get_last_synced_ns("bob") == 7_000

    def test_idempotent_on_repeated_calls(self, tmp_path: Path):
        legacy_path = tmp_path / "users_state.json"
        UserStateConfig(state={"alice": 42_000}).save(legacy_path)

        migrate_legacy_cursor(legacy_path)
        migrate_legacy_cursor(legacy_path)

        assert SyncedFile.objects.filter(username="alice").count() == 1
