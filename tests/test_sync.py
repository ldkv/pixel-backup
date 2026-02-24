import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from immich_backup.schemas import Settings, User, UserConfig
from immich_backup.sync import sync_all_users, sync_per_user
from immich_backup.utils import GIGABYTE


class TestSyncPerUser:
    def test_sync_basic_assets(self, tmp_path: Path):
        # Setup directories
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = immich_lib / "testuser"
        user_dir.mkdir(parents=True)

        # Create test files
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.jpg"
        file1.write_text("content1")
        file2.write_text("content2")

        configs = Settings(immich_library_dir=immich_lib, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, _ = sync_per_user(configs, user, user_quota_bytes)

        # Verify files were linked
        assert added_bytes > 0
        assert (syncthing_dir / "testuser" / "photo1.jpg").exists()
        assert (syncthing_dir / "testuser" / "photo2.jpg").exists()
        # Verify they are hard links (same inode on Linux/Windows compatible check)
        assert os.path.samefile(file1, syncthing_dir / "testuser" / "photo1.jpg")
        assert os.path.samefile(file2, syncthing_dir / "testuser" / "photo2.jpg")

    def test_sync_no_assets(self, tmp_path: Path):
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = immich_lib / "testuser"
        user_dir.mkdir(parents=True)

        configs = Settings(immich_library_dir=immich_lib, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, last_created_at = sync_per_user(configs, user, user_quota_bytes)

        assert added_bytes == 0
        assert last_created_at == user.asset_created_after.timestamp()

    def test_sync_skips_existing_destinations(self, tmp_path: Path):
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = immich_lib / "testuser"
        user_dir.mkdir(parents=True)

        # Create source file
        source_file = user_dir / "photo.jpg"
        source_file.write_text("original content")

        # Pre-create destination file
        dest_dir = syncthing_dir / "testuser"
        dest_dir.mkdir(parents=True)
        dest_file = dest_dir / "photo.jpg"
        dest_file.write_text("existing content")

        configs = Settings(immich_library_dir=immich_lib, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, _ = sync_per_user(configs, user, user_quota_bytes)

        # No bytes should be added since file was skipped
        assert added_bytes == 0
        # Destination should still have original content
        assert dest_file.read_text() == "existing content"

    def test_sync_respects_quota(self, tmp_path: Path):
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = immich_lib / "testuser"
        user_dir.mkdir(parents=True)

        # Create files with known sizes
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.jpg"
        file3 = user_dir / "photo3.jpg"
        file1.write_text("A" * 1000)  # 1000 bytes
        os.utime(file1, (datetime(2020, 1, 1).timestamp(), datetime(2020, 1, 1).timestamp()))
        file2.write_text("B" * 1000)  # 1000 bytes
        os.utime(file2, (datetime(2020, 1, 2).timestamp(), datetime(2020, 1, 2).timestamp()))
        file3.write_text("C" * 1000)  # 1000 bytes
        os.utime(file3, (datetime(2020, 1, 3).timestamp(), datetime(2020, 1, 3).timestamp()))

        configs = Settings(immich_library_dir=immich_lib, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 1500  # Should allow only 1-2 files before hitting quota

        added_bytes, last_created_at = sync_per_user(configs, user, user_quota_bytes)

        # Should stop after hitting quota
        assert added_bytes == 2000
        synced_files = [f.name for f in (syncthing_dir / "testuser").glob("*.jpg")]
        assert synced_files == ["photo2.jpg", "photo3.jpg"]
        assert last_created_at == pytest.approx(datetime(2020, 1, 3).timestamp(), abs=1)

    def test_sync_creates_nested_directories(self, tmp_path: Path):
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"
        nested_dir = immich_lib / "testuser" / "2024" / "01" / "photos"
        nested_dir.mkdir(parents=True)

        nested_file = nested_dir / "photo.jpg"
        nested_file.write_text("nested content")

        configs = Settings(immich_library_dir=immich_lib, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        sync_per_user(configs, user, user_quota_bytes)

        # Verify nested structure is preserved
        dest_file = syncthing_dir / "testuser" / "2024" / "01" / "photos" / "photo.jpg"
        assert dest_file.exists()
        assert os.path.samefile(nested_file, dest_file)


class TestSyncAllUsers:
    def test_sync_skips_when_above_lower_limit(self, tmp_path: Path):
        """Test that sync is skipped when folder is still full."""
        syncthing_dir = tmp_path / "syncthing"
        syncthing_dir.mkdir()

        # Create a large file to exceed lower limit
        large_file = syncthing_dir / "large.bin"
        large_file.write_bytes(b"X" * 6)

        settings = Settings(
            syncthing_dir=syncthing_dir,
            upper_limit_gb=10 / GIGABYTE,
            lower_limit_gb=5 / GIGABYTE,
        )

        with patch("immich_backup.sync.UserConfig.load"):
            sync_all_users(settings)
        assert len(list(syncthing_dir.rglob("*"))) == 1

    def test_sync_stops_when_quota_exhausted(self, tmp_path: Path):
        """Test that sync stops when running out of quota."""
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"

        # Create many users with files
        for i in range(5):
            user_dir = immich_lib / f"user{i}"
            user_dir.mkdir(parents=True)
            (user_dir / "photo.jpg").write_text("X" * 5)

        user_config = UserConfig(
            users=[User(username=f"user{i}", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC)) for i in range(5)]
        )

        with patch("immich_backup.sync.UserConfig.load") as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                immich_library_dir=immich_lib,
                syncthing_dir=syncthing_dir,
                upper_limit_gb=10 / GIGABYTE,  # Only enough for ~2 users
                lower_limit_gb=0.0,
            )

            sync_all_users(settings)

            # Not all users should have files synced due to quota limits
            synced_users = len(list(syncthing_dir.glob("user*")))
            assert synced_users < 5

    def test_sync_no_new_assets_for_any_user(self, tmp_path: Path):
        immich_lib = tmp_path / "immich_library"
        syncthing_dir = tmp_path / "syncthing"

        # Create user directory but no files
        user_dir = immich_lib / "testuser"
        user_dir.mkdir(parents=True)

        user_config = UserConfig(
            users=[User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))]
        )

        with patch("immich_backup.sync.UserConfig.load") as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                immich_library_dir=immich_lib,
                syncthing_dir=syncthing_dir,
                upper_limit_gb=1.0 / GIGABYTE,
                lower_limit_gb=0.0,
            )

            sync_all_users(settings)

            # No files should be created in syncthing dir
            assert not (syncthing_dir / "testuser").exists()
