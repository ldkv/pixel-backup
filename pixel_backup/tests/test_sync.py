import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from history.models import Batch, SyncedAsset, UserConfig
from pixel_backup.core.sync import link_with_retry, sync_all_users, sync_per_user
from pixel_backup.core.utils import consistent_dir
from pixel_backup.env import GIGABYTE, NANOSECONDS, Settings

pytestmark = pytest.mark.django_db


class TestSyncPerUser:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.syncthing_dir = tmp_path / "syncthing"
        self.username = "testuser"
        self.user_dir = tmp_path / self.username
        self.syncthing_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.user = UserConfig.objects.create(username=self.username, source_dir=str(self.user_dir), sync_order=1)

    def test_sync_basic_assets(self) -> None:
        # Create test files
        file1 = self.user_dir / "photo1.jpg"
        file2 = self.user_dir / "photo2.jpg"
        file1.write_text("content1")
        file2.write_text("content2")

        new_batch, new_assets = sync_per_user(self.syncthing_dir, self.user, 10000.0)

        # Verify files were linked
        assert new_batch.total_bytes == 16
        assert new_batch.files_count == 2
        assert {asset.source_path for asset in new_assets} == {file1.as_posix(), file2.as_posix()}
        for asset in new_assets:
            dest = Path(asset.dest_path)
            assert dest.parent.name == consistent_dir(self.user_dir)
            # Verify they are hard links (same inode on Linux/Windows compatible check)
            assert os.path.samefile(asset.source_path, dest)

    def test_sync_no_assets(self) -> None:
        new_batch, new_assets = sync_per_user(self.syncthing_dir, self.user, 1)

        assert new_batch.total_bytes == 0
        assert new_batch.files_count == 0
        assert new_assets == []

    def test_sync_skips_already_synced_source_paths(self) -> None:
        # Create source file
        source_file = self.user_dir / "photo.jpg"
        source_file.write_text("original content")

        # Mark it as already synced
        SyncedAsset.objects.create(
            user_config=self.user,
            source_path=source_file.as_posix(),
            dest_path="irrelevant",
            size_bytes=len("original content"),
            created_at_ns=0,
        )

        new_batch, new_assets = sync_per_user(self.syncthing_dir, self.user, 10000.0)

        # No bytes should be added since the source path was already synced
        assert new_batch.total_bytes == 0
        assert new_assets == []

    def test_sync_skips_asset_when_link_fails(self) -> None:
        file1 = self.user_dir / "photo1.jpg"
        file2 = self.user_dir / "photo2.jpg"
        file1.write_text("content1")
        file2.write_text("content22")
        now_ns = 1_700_000_000_000_000_000
        os.utime(file1, ns=(now_ns, now_ns))
        os.utime(file2, ns=(now_ns + NANOSECONDS, now_ns + NANOSECONDS))

        with (
            patch("pixel_backup.core.sync.link_with_retry", side_effect=[False, True]),
            patch("pixel_backup.core.sync.time.sleep"),
        ):
            new_batch, new_assets = sync_per_user(self.syncthing_dir, self.user, 10000.0)

        # Only the successfully-linked asset should be recorded; the failed one is not
        # counted, does not consume quota, and is not marked as synced.
        assert new_batch.files_count == 1
        assert new_batch.total_bytes == len("content22")
        assert {asset.source_path for asset in new_assets} == {file2.as_posix()}


class TestDryRun:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.syncthing_dir = tmp_path / "syncthing"
        self.username = "testuser"
        self.user_dir = tmp_path / self.username
        self.syncthing_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.user = UserConfig.objects.create(username=self.username, source_dir=str(self.user_dir), sync_order=1)

    def test_dry_run_does_not_create_links(self) -> None:
        file1 = self.user_dir / "photo1.jpg"
        file1.write_text("content1")

        new_batch, new_assets = sync_per_user(self.syncthing_dir, self.user, 10000.0, dry_run=True)

        assert new_batch.total_bytes > 0
        assert len(new_assets) == 1
        assert not (self.syncthing_dir / self.username).exists()

    def test_dry_run_does_not_persist_synced_assets(self) -> None:
        (self.user_dir / "photo.jpg").write_text("content")

        with patch("pixel_backup.core.sync.UserConfig.load", return_value=[self.user]):
            settings = Settings(syncthing_dir=self.syncthing_dir, phone_limit_gb=1.0 / GIGABYTE, stop_threshold_mb=0)
            sync_all_users(settings, dry_run=True)

        assert SyncedAsset.objects.count() == 0
        self.user.refresh_from_db()
        assert self.user.last_timestamp_ns == 0


class TestLinkWithRetry:
    def test_successful_link(self, tmp_path: Path) -> None:
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        link_with_retry(src, dest)

        assert dest.exists()
        assert os.path.samefile(src, dest)

    def test_retries_on_failure(self, tmp_path: Path) -> None:
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        call_count = 0
        original_link = os.link

        def flaky_link(s: str, d: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("Transient error")
            original_link(s, d)

        with (
            patch("pixel_backup.core.sync.os.link", side_effect=flaky_link),
            patch("pixel_backup.core.sync.time.sleep"),
        ):
            assert link_with_retry(src, dest, retries=3) is True

        assert call_count == 3

    def test_skips_after_max_retries(self, tmp_path: Path) -> None:
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"

        with (
            patch("pixel_backup.core.sync.os.link", side_effect=OSError("Permanent error")) as mock_link,
            patch("pixel_backup.core.sync.time.sleep"),
        ):
            assert link_with_retry(src, dest, retries=3) is False
            assert mock_link.call_count == 3


class TestSyncAllUsers:
    def setup_method(self) -> None:
        self.user_config_mock_path = "pixel_backup.core.sync.UserConfig.load"

    @patch("pixel_backup.core.sync.send_discord_notification")
    def test_sync_stops_when_quota_exhausted(self, mock_notify: Mock, tmp_path: Path) -> None:
        user_dir = tmp_path / "library"
        syncthing_dir = tmp_path / "syncthing"

        # Create many users with files
        users = []
        for i in range(5):
            source_dir = user_dir / f"user{i}"
            source_dir.mkdir(parents=True)
            (source_dir / "photo.jpg").write_text("X" * 5)
            users.append(UserConfig.objects.create(username=f"user{i}", source_dir=str(source_dir), sync_order=i))

        with patch(self.user_config_mock_path, return_value=users):
            settings = Settings(
                syncthing_dir=syncthing_dir,
                phone_limit_gb=10 / GIGABYTE,  # Only enough for ~2 users
                stop_threshold_mb=0,
            )

            sync_all_users(settings)

        # Not all users should have files synced due to quota limits
        synced_users = len(list(syncthing_dir.glob("user*")))
        assert synced_users == 2
        assert mock_notify.call_count == 2
        assert mock_notify.call_args_list[0].args[0].startswith("Reached upper limit of")
        assert mock_notify.call_args_list[1].args[0].startswith("Sync complete: 2 files")

    @patch("pixel_backup.core.sync.send_discord_notification")
    def test_sync_stops_batch_when_asset_exceeds_remaining_quota(self, mock_notify: Mock, tmp_path: Path) -> None:
        syncthing_dir = tmp_path / "syncthing"
        syncthing_dir.mkdir()
        # Pre-existing content leaves just 2 bytes of quota, not enough for the 10-byte photo below.
        (syncthing_dir / "existing.bin").write_bytes(b"X" * 8)

        user_dir = tmp_path / "testuser"
        user_dir.mkdir()
        (user_dir / "photo.jpg").write_bytes(b"X" * 10)
        user = UserConfig.objects.create(username="testuser", source_dir=str(user_dir), sync_order=1)

        with patch(self.user_config_mock_path, return_value=[user]):
            settings = Settings(syncthing_dir=syncthing_dir, phone_limit_gb=10 / GIGABYTE, stop_threshold_mb=0)

            sync_all_users(settings)

        assert not (syncthing_dir / "testuser").exists()
        assert mock_notify.call_count == 2
        assert mock_notify.call_args_list[0].args[0].startswith("Asset size is larger than remaining quota")
        assert mock_notify.call_args_list[1].args[0].startswith("Sync complete: 0 files")

    def test_dry_run_does_not_notify(self, tmp_path: Path) -> None:
        syncthing_dir = tmp_path / "syncthing"
        syncthing_dir.mkdir()
        (syncthing_dir / "big.bin").write_bytes(b"X" * 100)

        user_dir = tmp_path / "testuser"
        user_dir.mkdir()
        (user_dir / "photo.jpg").write_text("data")
        user = UserConfig.objects.create(username="testuser", source_dir=str(user_dir), sync_order=1)

        with (
            patch(self.user_config_mock_path, return_value=[user]),
            patch("pixel_backup.core.sync.send_discord_notification") as mock_notify,
        ):
            settings = Settings(syncthing_dir=syncthing_dir, phone_limit_gb=1 / GIGABYTE)
            sync_all_users(settings, dry_run=True)

        mock_notify.assert_not_called()

    def test_sync_no_new_assets_for_any_user(self, tmp_path: Path) -> None:
        syncthing_dir = tmp_path / "syncthing"
        # Create user directory but no files
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        user = UserConfig.objects.create(username="testuser", source_dir=str(user_dir), sync_order=1)

        with patch(self.user_config_mock_path, return_value=[user]):
            settings = Settings(syncthing_dir=syncthing_dir, phone_limit_gb=1.0 / GIGABYTE)

            sync_all_users(settings)

            # No files should be created in syncthing dir
            assert not (syncthing_dir / "testuser").exists()

    def test_sync_persists_batch_and_assets_and_advances_cursor(self, tmp_path: Path) -> None:
        syncthing_dir = tmp_path / "syncthing"
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.jpg"
        file1.write_bytes(b"X" * 5)
        file2.write_bytes(b"X" * 7)
        user = UserConfig.objects.create(username="testuser", source_dir=str(user_dir), sync_order=1)

        with patch(self.user_config_mock_path, return_value=[user]):
            settings = Settings(syncthing_dir=syncthing_dir, phone_limit_gb=1000 / GIGABYTE, stop_threshold_mb=0)
            sync_all_users(settings)

        assert Batch.objects.count() == 1
        batch = Batch.objects.get()
        assert batch.user_config_id == user.id
        assert batch.files_count == 2
        assert batch.total_bytes == 12

        assets = list(SyncedAsset.objects.all())
        assert len(assets) == 2
        assert {asset.batch_id for asset in assets} == {batch.id}

        user.refresh_from_db()
        max_created_at_ns = max(asset.created_at_ns for asset in assets)
        assert user.last_timestamp_ns == max_created_at_ns

    def test_sync_does_not_advance_cursor_past_asset_skipped_for_quota(self, tmp_path: Path) -> None:
        syncthing_dir = tmp_path / "syncthing"
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        small_file = user_dir / "small.jpg"
        large_file = user_dir / "large.jpg"
        later_file = user_dir / "later.jpg"
        small_file.write_bytes(b"X" * 3)
        large_file.write_bytes(b"X" * 100)
        later_file.write_bytes(b"X" * 3)

        # Force a deterministic mtime order: small (oldest) -> large -> later (newest).
        now_ns = 1_700_000_000_000_000_000
        os.utime(small_file, ns=(now_ns, now_ns))
        os.utime(large_file, ns=(now_ns + NANOSECONDS, now_ns + NANOSECONDS))
        os.utime(later_file, ns=(now_ns + 2_000_000_000, now_ns + 2_000_000_000))

        user = UserConfig.objects.create(username="testuser", source_dir=str(user_dir), sync_order=1)

        # Quota is only enough for the small file; the large one must be skipped.
        with patch(self.user_config_mock_path, return_value=[user]):
            settings = Settings(syncthing_dir=syncthing_dir, phone_limit_gb=3 / GIGABYTE, stop_threshold_mb=0)
            sync_all_users(settings)

        # Only the small file was synced; the loop stops at the oversized asset.
        synced_paths = set(SyncedAsset.objects.values_list("source_path", flat=True))
        assert synced_paths == {small_file.as_posix()}

        user.refresh_from_db()
        # The cursor must not advance past the skipped large asset's timestamp,
        # otherwise later.jpg (with a newer mtime) would be permanently missed.
        small_mtime_ns = small_file.stat().st_mtime_ns
        large_mtime_ns = large_file.stat().st_mtime_ns
        assert user.last_timestamp_ns == small_mtime_ns
        assert user.last_timestamp_ns < large_mtime_ns
