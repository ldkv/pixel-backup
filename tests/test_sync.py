import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from pixel_backup.schemas import Settings, User, UserConfig
from pixel_backup.sync import link_with_retry, sync_all_users, sync_per_user
from pixel_backup.utils import GIGABYTE


class TestSyncPerUser:
    def test_sync_basic_assets(self, tmp_path: Path):
        # Setup directories
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        # Create test files
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.jpg"
        file1.write_text("content1")
        file2.write_text("content2")

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, added_files, _ = sync_per_user(configs, user, user_quota_bytes)

        # Verify files were linked
        assert added_bytes > 0
        assert added_files == 2
        assert (syncthing_dir / "testuser" / "photo1.jpg").exists()
        assert (syncthing_dir / "testuser" / "photo2.jpg").exists()
        # Verify they are hard links (same inode on Linux/Windows compatible check)
        assert os.path.samefile(file1, syncthing_dir / "testuser" / "photo1.jpg")
        assert os.path.samefile(file2, syncthing_dir / "testuser" / "photo2.jpg")

    def test_sync_no_assets(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, added_files, last_created_at = sync_per_user(configs, user, user_quota_bytes)

        assert added_bytes == 0
        assert added_files == 0
        assert last_created_at == user.asset_created_after.timestamp() * 1_000_000_000

    def test_sync_skips_existing_destinations(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        # Create source file
        source_file = user_dir / "photo.jpg"
        source_file.write_text("original content")

        # Pre-create destination file
        dest_dir = syncthing_dir / "testuser"
        dest_dir.mkdir(parents=True)
        dest_file = dest_dir / "photo.jpg"
        dest_file.write_text("existing content")

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        added_bytes, added_files, _ = sync_per_user(configs, user, user_quota_bytes)

        # No bytes should be added since file was skipped
        assert added_bytes == 0
        assert added_files == 0
        assert dest_file.read_text() == "existing content"

    def test_sync_respects_quota(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        # Create files with known sizes
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.jpg"
        file3 = user_dir / "photo3.jpg"
        file1.write_text("A" * 1000)  # 1000 bytes
        os.utime(
            file1, (datetime(2019, 12, 31, tzinfo=UTC).timestamp(), datetime(2019, 12, 31, tzinfo=UTC).timestamp())
        )
        file2.write_text("B" * 1000)  # 1000 bytes
        os.utime(file2, (datetime(2020, 1, 2, tzinfo=UTC).timestamp(), datetime(2020, 1, 2, tzinfo=UTC).timestamp()))
        file3.write_text("C" * 1000)  # 1000 bytes
        os.utime(file3, (datetime(2020, 1, 3, tzinfo=UTC).timestamp(), datetime(2020, 1, 3, tzinfo=UTC).timestamp()))

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 1500  # Should allow only 1-2 files before hitting quota

        added_bytes, added_files, last_created_at = sync_per_user(configs, user, user_quota_bytes)

        # Should stop after hitting quota
        assert added_bytes == 2000
        assert added_files == 2
        synced_files = sorted(f.name for f in (syncthing_dir / "testuser").glob("*.jpg"))
        assert synced_files == ["photo2.jpg", "photo3.jpg"]
        assert last_created_at == datetime(2020, 1, 3, tzinfo=UTC).timestamp() * 1_000_000_000

    def test_sync_creates_nested_directories(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        nested_dir = library_dir / "testuser" / "2024" / "01" / "photos"
        nested_dir.mkdir(parents=True)

        nested_file = nested_dir / "photo.jpg"
        nested_file.write_text("nested content")

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))
        user_quota_bytes = 10000.0

        sync_per_user(configs, user, user_quota_bytes)

        # Verify nested structure is preserved
        dest_file = syncthing_dir / "testuser" / "2024" / "01" / "photos" / "photo.jpg"
        assert dest_file.exists()
        assert os.path.samefile(nested_file, dest_file)


class TestDryRun:
    def test_dry_run_does_not_create_links(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        file1 = user_dir / "photo1.jpg"
        file1.write_text("content1")

        configs = Settings(library_dir=library_dir, syncthing_dir=syncthing_dir)
        user = User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))

        added_bytes, added_files, _ = sync_per_user(configs, user, 10000.0, dry_run=True)

        assert added_bytes > 0
        assert added_files == 1
        assert not (syncthing_dir / "testuser" / "photo1.jpg").exists()

    def test_dry_run_does_not_update_user_config(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        (user_dir / "photo.jpg").write_text("content")

        user_config = UserConfig(
            users=[User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))]
        )
        original_ts = user_config.users[0].last_timestamp_ns

        with patch("pixel_backup.sync.UserConfig.load") as mock_load:
            mock_load.return_value = user_config
            settings = Settings(
                library_dir=library_dir,
                syncthing_dir=syncthing_dir,
                upper_limit_gb=1.0 / GIGABYTE,
                lower_limit_gb=0.0,
            )
            sync_all_users(settings, dry_run=True)

        assert user_config.users[0].last_timestamp_ns == original_ts


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
        ):
            try:
                link_with_retry(src, dest, retries=3)
                assert False, "Should have raised OSError"
            except OSError:
                pass


class TestSyncAllUsers:
    def setup_method(self):
        self.user_config_mock_path = "pixel_backup.sync.UserConfig.load"

    def test_sync_skips_when_above_lower_limit(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        syncthing_dir = tmp_path / "syncthing"
        syncthing_dir.mkdir()

        # Create a large file to exceed lower limit
        large_file = syncthing_dir / "large.bin"
        large_file.write_bytes(b"X" * 6)

        settings = Settings(
            library_dir=library_dir,
            syncthing_dir=syncthing_dir,
            upper_limit_gb=10 / GIGABYTE,
            lower_limit_gb=5 / GIGABYTE,
        )

        with patch(self.user_config_mock_path):
            sync_all_users(settings)
        assert len(list(syncthing_dir.rglob("*"))) == 1

    def test_sync_stops_when_quota_exhausted(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"

        # Create many users with files
        for i in range(5):
            user_dir = library_dir / f"user{i}"
            user_dir.mkdir(parents=True)
            (user_dir / "photo.jpg").write_text("X" * 5)

        user_config = UserConfig(
            users=[User(username=f"user{i}", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC)) for i in range(5)]
        )

        with patch(self.user_config_mock_path) as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                library_dir=library_dir,
                syncthing_dir=syncthing_dir,
                upper_limit_gb=10 / GIGABYTE,  # Only enough for ~2 users
                lower_limit_gb=0.0,
            )

            sync_all_users(settings)

            # Not all users should have files synced due to quota limits
            synced_users = len(list(syncthing_dir.glob("user*")))
            assert synced_users < 5

    def test_sync_no_new_assets_for_any_user(self, tmp_path: Path):
        library_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"

        # Create user directory but no files
        user_dir = library_dir / "testuser"
        user_dir.mkdir(parents=True)

        user_config = UserConfig(
            users=[User(username="testuser", asset_created_after=datetime(2020, 1, 1, tzinfo=UTC))]
        )

        with patch(self.user_config_mock_path) as mock_load:
            mock_load.return_value = user_config

            settings = Settings(
                library_dir=library_dir,
                syncthing_dir=syncthing_dir,
                upper_limit_gb=1.0 / GIGABYTE,
                lower_limit_gb=0.0,
            )

            sync_all_users(settings)

            # No files should be created in syncthing dir
            assert not (syncthing_dir / "testuser").exists()
