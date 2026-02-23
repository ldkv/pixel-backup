import json
from datetime import datetime
from pathlib import Path

import pytest

from immich_backup.schemas import User, UserSync


class TestUserSync:
    def test_load_from_existing_file(self, tmp_path: Path):
        """Test loading UserSync from an existing JSON file."""
        users_file = tmp_path / "users.json"
        test_data = {
            "users": [
                {
                    "username": "testuser",
                    "immich_api_key": "secret123",
                    "asset_created_after": "2024-01-01T00:00:00",
                    "last_asset_id": 42,
                }
            ]
        }
        users_file.write_text(json.dumps(test_data))

        user_sync = UserSync.load(users_file)

        assert len(user_sync.users) == 1
        assert user_sync.users[0].username == "testuser"
        assert user_sync.users[0].immich_api_key == "secret123"
        assert user_sync.users[0].asset_created_after == datetime(2024, 1, 1)
        assert user_sync.users[0].last_asset_id == 42

    def test_load_from_nonexistent_file(self, tmp_path: Path):
        """Test loading from a non-existent file raises FileNotFoundError."""
        nonexistent_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Users settings file not found"):
            UserSync.load(nonexistent_file)

    def test_save_to_file(self, tmp_path: Path):
        """Test saving UserSync to a JSON file."""
        users_file = tmp_path / "users.json"
        user_sync = UserSync(
            users=[
                User(
                    username="alice",
                    immich_api_key="key123",
                    asset_created_after=datetime(2023, 6, 15, 10, 30),
                    last_asset_id=100,
                )
            ]
        )

        user_sync.save(users_file)
        assert users_file.exists()
        saved_data = json.loads(users_file.read_text())
        assert saved_data["users"][0]["username"] == "alice"
        assert saved_data["users"][0]["immich_api_key"] == "key123"
        assert saved_data["users"][0]["asset_created_after"] == "2023-06-15T10:30:00"
        assert saved_data["users"][0]["last_asset_id"] == 100

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        """Test that saving and loading preserves data."""
        users_file = tmp_path / "users.json"
        original = UserSync(
            users=[
                User(
                    username="bob",
                    immich_api_key="secret456",
                    asset_created_after=datetime(2025, 3, 20, 14, 45, 30),
                    last_asset_id=999,
                ),
                User(
                    username="charlie",
                    immich_api_key="supersecret",
                    asset_created_after=datetime(2022, 12, 1),
                    last_asset_id=5,
                ),
            ]
        )

        original.save(users_file)
        loaded = UserSync.load(users_file)

        assert len(loaded.users) == 2
        assert loaded.users[0].username == "bob"
        assert loaded.users[0].immich_api_key == "secret456"
        assert loaded.users[0].asset_created_after == datetime(2025, 3, 20, 14, 45, 30)
        assert loaded.users[0].last_asset_id == 999
        assert loaded.users[1].username == "charlie"
        assert loaded.users[1].immich_api_key == "supersecret"
        assert loaded.users[1].asset_created_after == datetime(2022, 12, 1)
        assert loaded.users[1].last_asset_id == 5

    def test_empty_users_list(self, tmp_path: Path):
        """Test UserSync with empty users list."""
        users_file = tmp_path / "users.json"
        user_sync = UserSync(users=[])

        user_sync.save(users_file)
        loaded = UserSync.load(users_file)

        assert len(loaded.users) == 0

    def test_user_defaults(self):
        """Test User model with default values."""
        user = User(username="defaultuser", immich_api_key="key")

        assert user.username == "defaultuser"
        assert user.immich_api_key == "key"
        assert user.asset_created_after == datetime(1970, 1, 1)
        assert user.last_asset_id == 0

    def test_json_formatting(self, tmp_path: Path):
        """Test that saved JSON is properly formatted with indentation."""
        users_file = tmp_path / "users.json"
        user_sync = UserSync(users=[User(username="test", immich_api_key="key")])

        user_sync.save(users_file)

        content = users_file.read_text()
        # Check that JSON is indented (has newlines and spaces)
        assert "\n" in content
        assert "    " in content
