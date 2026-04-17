import os
import time
from pathlib import Path

from pixel_backup.local_disk import fetch_local_assets, is_media_file


class TestIsMediaFile:
    def test_valid_media_files(self, tmp_path: Path):
        media_files = [
            "photo.jpg",
            "photo.JPG",
            "video.mp4",
            "video.MP4",
            "image.png",
            "image.PNG",
            "photo.heic",
            "photo.HEIC",
            "video.mov",
            "video.MOV",
            "raw.dng",
            "raw.DNG",
            "noextension",
        ]

        for filename in media_files:
            file_path = tmp_path / filename
            file_path.touch()
            assert is_media_file(file_path.name), f"{filename} should be recognized as media file"

    def test_ignored_extensions(self, tmp_path: Path):
        ignored_files = [
            "metadata.xmp",
            "metadata.XMP",
            "data.immich",
            "config.json",
            "config.JSON",
            "settings.yaml",
            "settings.yml",
            "file.trashed",
            "database.db",
            "config.ini",
            "output.log",
            "temp.tmp",
        ]

        for filename in ignored_files:
            file_path = tmp_path / filename
            file_path.touch()
            assert not is_media_file(file_path.name), f"{filename} should be ignored"


class TestFetchLocalAssets:
    def test_fetch_from_valid_user_directory(self, tmp_path: Path):
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        # Create some media files with different timestamps
        file1 = user_dir / "photo1.jpg"
        file2 = user_dir / "photo2.png"
        file1.write_text("content1")
        file2.write_text("content2")

        # Set modified times
        file1.touch()
        file2.touch()

        # Fetch all assets (created_after = 0)
        assets = fetch_local_assets(user_dir, 0)

        assert len(assets) == 2
        assert all(isinstance(asset, tuple) and len(asset) == 3 for asset in assets)
        # Check that returned tuples contain (Path, size, timestamp)
        paths = [asset[0] for asset in assets]
        assert file1 in paths
        assert file2 in paths

    def test_fetch_with_timestamp_filter(self, tmp_path: Path):
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        # Create an old file
        old_file = user_dir / "old.jpg"
        old_file.write_text("old")
        old_time = time.time() - 10000  # 10000 seconds ago
        os.utime(old_file, (old_time, old_time))

        # Create a new file
        new_file = user_dir / "new.jpg"
        new_file.write_text("new")
        new_file.touch()  # Current time

        # Fetch only recent assets
        cutoff_time = int((time.time() - 5000) * 1_000_000_000)  # Convert to nanoseconds
        assets = fetch_local_assets(user_dir, cutoff_time)

        # Should only get the new file
        assert len(assets) == 1
        assert assets[0][0] == new_file

    def test_user_path_is_file_not_directory(self, tmp_path: Path):
        # Create a file instead of directory
        user_file = tmp_path / "testuser"
        user_file.write_text("not a directory")

        assets = fetch_local_assets(user_file, 0)

        assert assets == []

    def test_nested_directory_structure(self, tmp_path: Path):
        user_dir = tmp_path / "testuser"
        nested_dir = user_dir / "2024" / "01" / "photos"
        nested_dir.mkdir(parents=True)

        # Create files at different nesting levels
        root_file = user_dir / "root.jpg"
        mid_file = user_dir / "2024" / "mid.jpg"
        deep_file = nested_dir / "deep.jpg"

        root_file.write_text("root")
        mid_file.write_text("mid")
        deep_file.write_text("deep")

        assets = fetch_local_assets(user_dir, 0)

        assert len(assets) == 3
        paths = [asset[0] for asset in assets]
        assert root_file in paths
        assert mid_file in paths
        assert deep_file in paths

    def test_ignored_files_not_included(self, tmp_path: Path):
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        # Create media files
        media1 = user_dir / "photo.jpg"
        media2 = user_dir / "video.mp4"
        media1.write_text("photo")
        media2.write_text("video")

        # Create ignored files
        ignored1 = user_dir / "metadata.xmp"
        ignored2 = user_dir / "config.json"
        ignored3 = user_dir / "data.immich"
        ignored1.write_text("meta")
        ignored2.write_text("{}")
        ignored3.write_text("data")

        assets = fetch_local_assets(user_dir, 0)

        # Should only get media files
        assert len(assets) == 2
        paths = [asset[0] for asset in assets]
        assert media1 in paths
        assert media2 in paths
        assert ignored1 not in paths
        assert ignored2 not in paths
        assert ignored3 not in paths

    def test_return_tuple_structure(self, tmp_path: Path):
        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)

        file_path = user_dir / "test.jpg"
        content = "A" * 1024  # 1 KB
        file_path.write_text(content)
        current_time = time.time()
        os.utime(file_path, (current_time, current_time))

        assets = fetch_local_assets(user_dir, 0)

        assert len(assets) == 1
        path, size, timestamp = assets[0]

        assert path == file_path
        assert size == 1024
        assert timestamp / 1_000_000_000 == current_time
