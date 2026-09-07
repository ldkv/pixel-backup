import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from pixel_backup.schemas import UserStateConfig


class SyncedFile(NamedTuple):
    source_path: Path
    dest_path: Path
    size_bytes: int
    asset_created_at_ns: int


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            files_count INTEGER NOT NULL,
            total_bytes INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS synced_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER REFERENCES batches(id),
            username TEXT NOT NULL,
            source_path TEXT NOT NULL,
            dest_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            asset_created_at_ns INTEGER NOT NULL,
            UNIQUE(username, source_path)
        );

        CREATE INDEX IF NOT EXISTS idx_synced_files_username ON synced_files(username);
    """)
    conn.commit()


def is_synced(conn: sqlite3.Connection, username: str, source_path: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM synced_files WHERE username = ? AND source_path = ?",
        (username, source_path),
    ).fetchone()
    return row is not None


def get_last_synced_ns(conn: sqlite3.Connection, username: str) -> int:
    row = conn.execute(
        "SELECT MAX(asset_created_at_ns) FROM synced_files WHERE username = ?",
        (username,),
    ).fetchone()
    return row[0] if row and row[0] is not None else 0


def record_batch(conn: sqlite3.Connection, username: str, synced_files: list[SyncedFile]) -> None:
    total_bytes = sum(f.size_bytes for f in synced_files)
    with conn:
        cursor = conn.execute(
            "INSERT INTO batches (username, synced_at, files_count, total_bytes) VALUES (?, ?, ?, ?)",
            (username, datetime.now(UTC).isoformat(), len(synced_files), total_bytes),
        )
        batch_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO synced_files "
            "(batch_id, username, source_path, dest_path, size_bytes, asset_created_at_ns) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    batch_id,
                    username,
                    f.source_path.as_posix(),
                    f.dest_path.as_posix(),
                    f.size_bytes,
                    f.asset_created_at_ns,
                )
                for f in synced_files
            ],
        )


def migrate_legacy_cursor(conn: sqlite3.Connection, legacy_path: Path) -> None:
    """One-time bootstrap of the sync cursor from the old users_state.json. Idempotent via
    INSERT OR IGNORE + the (username, source_path) unique constraint, so it's safe to call
    on every startup."""
    if not legacy_path.exists():
        return

    state = UserStateConfig.load(path=legacy_path, generate_default=False)
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO synced_files "
            "(batch_id, username, source_path, dest_path, size_bytes, asset_created_at_ns) "
            "VALUES (NULL, ?, ?, '', 0, ?)",
            [(username, f"__migrated_cursor__:{username}", last_ns) for username, last_ns in state.state.items()],
        )
