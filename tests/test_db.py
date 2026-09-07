from pathlib import Path

from pixel_backup.db import (
    SyncedFile,
    connect,
    get_last_synced_ns,
    init_db,
    is_synced,
    migrate_legacy_cursor,
    record_batch,
)
from pixel_backup.schemas import UserStateConfig


def make_conn(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    return conn


class TestInitDb:
    def test_creates_tables(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"batches", "synced_files"} <= tables

    def test_idempotent(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        init_db(conn)  # should not raise


class TestIsSynced:
    def test_false_when_absent(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        assert is_synced(conn, "alice", "/library/alice/photo.jpg") is False

    def test_true_after_record_batch(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        record_batch(
            conn,
            "alice",
            [SyncedFile(Path("/library/alice/photo.jpg"), Path("/dest/photo.jpg"), 100, 1_000)],
        )
        assert is_synced(conn, "alice", "/library/alice/photo.jpg") is True
        assert is_synced(conn, "bob", "/library/alice/photo.jpg") is False


class TestGetLastSyncedNs:
    def test_zero_when_empty(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        assert get_last_synced_ns(conn, "alice") == 0

    def test_returns_max(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        record_batch(
            conn,
            "alice",
            [
                SyncedFile(Path("/library/alice/a.jpg"), Path("/dest/a.jpg"), 100, 1_000),
                SyncedFile(Path("/library/alice/b.jpg"), Path("/dest/b.jpg"), 100, 5_000),
            ],
        )
        assert get_last_synced_ns(conn, "alice") == 5_000


class TestRecordBatch:
    def test_writes_batch_and_files(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        files = [
            SyncedFile(Path("/library/alice/a.jpg"), Path("/dest/a.jpg"), 100, 1_000),
            SyncedFile(Path("/library/alice/b.jpg"), Path("/dest/b.jpg"), 200, 2_000),
        ]
        record_batch(conn, "alice", files)

        batches = conn.execute("SELECT username, files_count, total_bytes FROM batches").fetchall()
        assert batches == [("alice", 2, 300)]

        rows = conn.execute("SELECT source_path, batch_id FROM synced_files ORDER BY source_path").fetchall()
        assert [r[0] for r in rows] == ["/library/alice/a.jpg", "/library/alice/b.jpg"]
        assert rows[0][1] == rows[1][1]


class TestMigrateLegacyCursor:
    def test_noop_when_legacy_file_missing(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        migrate_legacy_cursor(conn, tmp_path / "missing.json")
        assert get_last_synced_ns(conn, "alice") == 0

    def test_seeds_cursor_from_legacy_state(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        legacy_path = tmp_path / "users_state.json"
        UserStateConfig(state={"alice": 42_000, "bob": 7_000}).save(legacy_path)

        migrate_legacy_cursor(conn, legacy_path)

        assert get_last_synced_ns(conn, "alice") == 42_000
        assert get_last_synced_ns(conn, "bob") == 7_000

    def test_idempotent_on_repeated_calls(self, tmp_path: Path):
        conn = make_conn(tmp_path)
        legacy_path = tmp_path / "users_state.json"
        UserStateConfig(state={"alice": 42_000}).save(legacy_path)

        migrate_legacy_cursor(conn, legacy_path)
        migrate_legacy_cursor(conn, legacy_path)

        count = conn.execute("SELECT COUNT(*) FROM synced_files WHERE username = 'alice'").fetchone()[0]
        assert count == 1
