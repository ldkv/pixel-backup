import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pixel_backup.env import Settings
from pixel_backup.history.repository import PendingFile, get_last_synced_ns, is_synced, record_batch
from pixel_backup.schemas import User, UserConfig
from pixel_backup.sync import link_with_retry, sync_all_users, sync_per_source
from pixel_backup.utils import GIGABYTE, consistent_dir, generate_destination_path

pytestmark = pytest.mark.django_db


class TestSyncPerUser:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path):
        self.syncthing_dir = tmp_path / "syncthing"
        self.username = "testuser"
        self.user_dir = tmp_path / self.username
        self.syncthing_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.fixed_args = (self.syncthing_dir, self.username, self.user_dir)

    def test_sync_basic_assets(self):
        # Create test files
        file1 = self.user_dir / "photo1.jpg"
        file2 = self.user_dir / "photo2.jpg"
        file1.write_text("content1")
        file2.write_text("content2")

        added_bytes, synced_files = sync_per_source(*self.fixed_args, 0, 10000.0)

        # Verify files were linked
        assert added_bytes == 16
        assert (
            synced_files[0].dest_path.parent.name
            == synced_files[1].dest_path.parent.name
            == consistent_dir(self.user_dir)
        )
        # Verify they are hard links (same inode on Linux/Windows compatible check)
        assert os.path.samefile(file1, synced_files[0].dest_path)
        assert os.path.samefile(file2, synced_files[1].dest_path)

    def test_sync_no_assets(self):
        added_bytes, synced_files = sync_per_source(*self.fixed_args, 0, 1)

        assert added_bytes == 0
        assert synced_files == []

    def test_sync_skips_existing_destinations(self):
        # Create source file
        source_file = self.user_dir / "photo.jpg"
        source_file.write_text("original content")

        # Pre-create destination file
        dest_path = generate_destination_path(self.syncthing_dir / self.username, source_file)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text("existing content")

        added_bytes, synced_files = sync_per_source(*self.fixed_args, 0, 10000.0)

        # No bytes should be added since file was skipped
        assert added_bytes == 0
        assert synced_files == []
        assert dest_path.read_text() == "existing content"

    def test_sync_skips_already_recorded_files(self):
        source_file = self.user_dir / "photo.jpg"
        source_file.write_text("content")
        record_batch(
            self.username,
            [PendingFile(source_file, self.syncthing_dir / "photo.jpg", 7, 1_000)],
        )

        added_bytes, synced_files = sync_per_source(*self.fixed_args, 0, 10000.0)

        assert added_bytes == 0
        assert synced_files == []


class TestDryRun:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.syncthing_dir = tmp_path / "syncthing"
        self.username = "testuser"
        self.user_dir = tmp_path / self.username
        self.syncthing_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.fixed_args = (self.syncthing_dir, self.username, self.user_dir)

    def test_dry_run_does_not_create_links(self):
        file1 = self.user_dir / "photo1.jpg"
        file1.write_text("content1")

        added_bytes, synced_files = sync_per_source(*self.fixed_args, 0, 10000.0, dry_run=True)

        assert added_bytes > 0
        assert len(synced_files) == 1
        assert not (self.syncthing_dir / "testuser").exists()

    def test_dry_run_does_not_persist_history(self):
        (self.user_dir / "photo.jpg").write_text("content")
        user_config = UserConfig(
            users=[
                User(
                    username="testuser",
                    source_dir=self.user_dir,
                    asset_created_after=datetime(2020, 1, 1, tzinfo=UTC),
                )
            ]
        )

        with patch("pixel_backup.sync.UserConfig.load") as mock_load:
            mock_load.return_value = user_config
            settings = Settings(
                syncthing_dir=self.syncthing_dir,
                upper_limit_gb=1.0 / GIGABYTE,
            )
            sync_all_users(settings, dry_run=True)

        assert get_last_synced_ns("testuser") == 0
        assert is_synced("testuser", (self.user_dir / "photo.jpg").as_posix()) is False


class TestLinkWithRetry:
    def test_successful_link(self, tmp_path: Path):
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        link_with_retry(src, dest)

        assert dest.exists()
        assert os.path.samefile(src, dest)

    def test_retries_on_failure(self, tmp_path: Path):
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        call_count = 0
        original_link = os.link

        def flaky_link(s, d):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("Transient error")
            original_link(s, d)

        with patch("pixel_backup.sync.os.link", side_effect=flaky_link), patch("pixel_backup.sync.time.sleep"):
            link_with_retry(src, dest, retries=3)

        assert call_count == 3

    def test_raises_after_max_retries(self, tmp_path: Path):
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        with (
            patch("pixel_backup.sync.os.link", side_effect=OSError("Permanent error")),
            patch("pixel_backup.sync.time.sleep"),
            pytest.raises(OSError),
        ):
            link_with_retry(src, dest, retries=3)


class TestSyncAllUsers:
    def setup_method(self):
        self.user_config_mock_path = "pixel_backup.sync.UserConfig.load"

    @patch("pixel_backup.sync.send_discord_notification")
    def test_sync_stops_when_quota_exhausted(self, mock_notify: Mock, tmp_path: Path):
        user_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"

        # Create many users with files
        user_dirs = []
        for i in range(5):
            source_dir = user_dir / f"user{i}"
            source_dir.mkdir(parents=True)
            (source_dir / "photo.jpg").write_text("X" * 5)
            user_dirs.append(source_dir)

        user_config = UserConfig(
            users=[
                User(
                    username=f"user{i}",
                    source_dir=user_dirs[i],
                    asset_created_after=datetime(2020, 1, 1, tzinfo=UTC),
                )
                for i in range(5)
            ]
        )

        with patch(self.user_config_mock_path) as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                syncthing_dir=syncthing_dir,
                upper_limit_gb=10 / GIGABYTE,  # Only enough for ~2 users
            )

            sync_all_users(settings)

            # Not all users should have files synced due to quota limits
            synced_users = len(list(syncthing_dir.glob("user*")))
            assert synced_users == 2
            assert mock_notify.call_count == 2
            assert mock_notify.call_args_list[0].args[0].startswith("Reached upper limit of")
            assert mock_notify.call_args_list[1].args[0].startswith("Sync complete: 2 files")

    def test_dry_run_does_not_notify(self, tmp_path: Path):
        syncthing_dir = tmp_path / "syncthing"
        syncthing_dir.mkdir()
        (syncthing_dir / "big.bin").write_bytes(b"X" * 100)

        user_dir = tmp_path / "testuser"
        user_dir.mkdir()
        (user_dir / "photo.jpg").write_text("data")
        user_config = UserConfig(
            users=[
                User(
                    username="testuser",
                    source_dir=user_dir,
                    asset_created_after=datetime(2020, 1, 1, tzinfo=UTC),
                )
            ]
        )

        with (
            patch(self.user_config_mock_path) as mock_load,
            patch("pixel_backup.sync.send_discord_notification") as mock_notify,
        ):
            mock_load.return_value = user_config
            settings = Settings(
                syncthing_dir=syncthing_dir,
                upper_limit_gb=1 / GIGABYTE,
            )
            sync_all_users(settings, dry_run=True)

        mock_notify.assert_not_called()

    def test_sync_no_new_assets_for_any_user(self, tmp_path: Path):
        syncthing_dir = tmp_path / "syncthing"
        # Create user directory but no files
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        user_config = UserConfig(
            users=[
                User(
                    username="testuser",
                    source_dir=user_dir,
                    asset_created_after=datetime(2020, 1, 1, tzinfo=UTC),
                )
            ]
        )

        with patch(self.user_config_mock_path) as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                syncthing_dir=syncthing_dir,
                upper_limit_gb=1.0 / GIGABYTE,
            )

            sync_all_users(settings)

            # No files should be created in syncthing dir
            assert not (syncthing_dir / "testuser").exists()
