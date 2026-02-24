import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from immich_backup.schemas import User, UserConfig


def test_load_from_existing_file(tmp_path: Path):
    """Test loading UserSync from an existing JSON file."""
    users_file = tmp_path / "users.json"
    test_data = {
        "users": [
            {
                "username": "testuser",
                "asset_created_after": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    users_file.write_text(json.dumps(test_data))

    user_sync = UserConfig.load(path=users_file, generate_default=False)

    assert len(user_sync.users) == 1
    assert user_sync.users[0].username == "testuser"
    assert user_sync.users[0].asset_created_after == datetime(2024, 1, 1, tzinfo=UTC)


def test_load_from_nonexistent_file(tmp_path: Path):
    """Test loading from a non-existent file raises FileNotFoundError."""
    nonexistent_file = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError, match="Config file not found"):
        UserConfig.load(path=nonexistent_file, generate_default=False)


def test_save_to_file(tmp_path: Path):
    """Test saving UserSync to a JSON file."""
    users_file = tmp_path / "users.json"
    user_sync = UserConfig(
        users=[
            User(
                username="alice",
                asset_created_after=datetime(2023, 6, 15, 10, 30, tzinfo=UTC),
            )
        ]
    )

    user_sync.save(users_file)
    assert users_file.exists()
    saved_data = json.loads(users_file.read_text())
    assert saved_data["users"][0]["username"] == "alice"
    assert saved_data["users"][0]["asset_created_after"] == "2023-06-15T10:30:00Z"


def test_save_and_load_roundtrip(tmp_path: Path):
    """Test that saving and loading preserves data."""
    users_file = tmp_path / "users.json"
    original = UserConfig(
        users=[
            User(username="bob", asset_created_after=datetime(2025, 3, 20, 14, 45, 30, tzinfo=UTC)),
            User(username="charlie", asset_created_after=datetime(2022, 12, 1, tzinfo=UTC)),
        ]
    )

    original.save(users_file)
    loaded = UserConfig.load(users_file)

    assert len(loaded.users) == 2
    assert loaded.users[0].username == "bob"
    assert loaded.users[0].asset_created_after == datetime(2025, 3, 20, 14, 45, 30, tzinfo=UTC)
    assert loaded.users[1].username == "charlie"
    assert loaded.users[1].asset_created_after == datetime(2022, 12, 1, tzinfo=UTC)


def test_empty_users_list(tmp_path: Path):
    """Test UserSync with empty users list."""
    users_file = tmp_path / "users.json"
    user_sync = UserConfig(users=[])

    user_sync.save(users_file)
    loaded = UserConfig.load(users_file)

    assert len(loaded.users) == 0


def test_user_defaults():
    """Test User model with default values."""
    user = User(username="defaultuser")
    assert user.username == "defaultuser"
    assert user.asset_created_after == datetime(1970, 1, 1, tzinfo=UTC)
