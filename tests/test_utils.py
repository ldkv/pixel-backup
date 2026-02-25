from datetime import UTC, datetime
from pathlib import Path

import pytest

from pixel_backup.utils import GIGABYTE, get_folder_size_gb, seconds_until_next_cron


class TestSecondsUntilNextCron:
    def test_next_cron_basic(self):
        # Every hour at minute 0: "0 * * * *"
        current_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
        cron_schedule = "0 * * * *"
        min_sleep = 1

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Next execution is at 11:00, which is 30 minutes = 1800 seconds away
        assert result == 1800.0

    def test_next_cron_daily_midnight(self):
        # Daily at midnight: "0 0 * * *"
        current_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
        cron_schedule = "0 0 * * *"
        min_sleep = 1

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Next execution is at midnight tomorrow (13.5 hours = 48600 seconds)
        assert result == 48600.0

    def test_min_sleep_seconds_applied(self):
        # Every minute: "* * * * *"
        current_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
        cron_schedule = "* * * * *"
        min_sleep = 300  # 5 minutes

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Next cron would be in 60 seconds, but min_sleep enforces 300
        assert result == 300

    def test_min_sleep_not_applied_when_cron_larger(self):
        # Every 10 minutes: "*/10 * * * *"
        current_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        cron_schedule = "*/10 * * * *"
        min_sleep = 60

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Next execution is in 10 minutes = 600 seconds
        assert result == 600.0

    def test_cron_at_exact_time(self):
        # Every hour at minute 0
        current_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        cron_schedule = "0 * * * *"
        min_sleep = 1

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Should get the NEXT occurrence, which is in 1 hour
        assert result == 3600.0

    def test_weekly_schedule(self):
        # Every Monday at 3am: "0 3 * * 1"
        # Starting on Sunday 2024-01-07 at 10:30
        current_time = datetime(2024, 1, 7, 10, 30, 0, tzinfo=UTC)
        cron_schedule = "0 3 * * 1"
        min_sleep = 1

        result = seconds_until_next_cron(cron_schedule, current_time, min_sleep)

        # Next Monday is 2024-01-08 at 3am, which is 16.5 hours away
        assert result == 59400.0


class TestGetFolderSizeGb:
    def test_empty_folder(self, tmp_path: Path):
        result = get_folder_size_gb(tmp_path)
        assert result == 0.0

    def test_single_file(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        content = "A" * 1024  # 1 KB
        test_file.write_text(content)

        result = get_folder_size_gb(tmp_path)
        expected = 1024 / GIGABYTE
        assert result == expected

    def test_multiple_files(self, tmp_path: Path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("A" * 2048)  # 2 KB
        file2.write_text("B" * 3072)  # 3 KB

        result = get_folder_size_gb(tmp_path)
        expected = 5120 / GIGABYTE  # 5 KB total
        assert result == expected

    def test_nested_directories(self, tmp_path: Path):
        subdir1 = tmp_path / "subdir1"
        subdir2 = subdir1 / "subdir2"
        subdir2.mkdir(parents=True)

        file1 = tmp_path / "root.txt"
        file2 = subdir1 / "level1.txt"
        file3 = subdir2 / "level2.txt"

        file1.write_text("A" * 1024)
        file2.write_text("B" * 2048)
        file3.write_text("C" * 4096)

        result = get_folder_size_gb(tmp_path)
        expected = 7168 / GIGABYTE  # 7 KB total
        assert result == expected

    def test_ignores_symlinks(self, tmp_path: Path):
        # Create a regular file
        real_file = tmp_path / "real.txt"
        real_file.write_text("A" * 1024)

        # Create a symlink to the file
        symlink = tmp_path / "link.txt"
        try:
            symlink.symlink_to(real_file)

            result = get_folder_size_gb(tmp_path)
            # Should only count the real file once, not the symlink
            expected = 1024 / GIGABYTE
            assert result == expected
        except OSError:
            # Skip test if symlinks aren't supported (Windows without admin)
            pytest.skip("Symlinks not supported on this system")

    def test_large_file_size_calculation(self, tmp_path: Path):
        large_file = tmp_path / "large.bin"
        size_bytes = 1024 * 1024  # 1 MB
        large_file.write_bytes(b"X" * size_bytes)

        result = get_folder_size_gb(tmp_path)
        expected = size_bytes / GIGABYTE
        assert result == pytest.approx(expected, rel=1e-9)

    def test_empty_subdirectories_dont_affect_size(self, tmp_path: Path):
        subdir1 = tmp_path / "empty1"
        subdir2 = tmp_path / "empty2" / "nested"
        subdir1.mkdir()
        subdir2.mkdir(parents=True)

        result = get_folder_size_gb(tmp_path)
        assert result == 0.0
