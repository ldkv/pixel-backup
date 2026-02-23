import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=False)


def setup_syncthing_config() -> None:
    """Generate and configure Syncthing if config doesn't exist."""
    config_path = Path("/var/lib/syncthing/config.xml")

    if config_path.exists():
        print("Syncthing config already exists, skipping setup")
        return

    print("Generating Syncthing config...")

    # Get environment variables
    st_key = os.environ.get("ST_KEY", "")
    st_pixel_id = os.environ.get("ST_PIXEL_ID", "")
    st_folder_id = os.environ.get("ST_FOLDER_ID", "")
    sync_dir = os.environ.get("SYNC_DIR", "/sync")

    # Generate config
    run_command(["syncthing", "generate", "--home=/var/lib/syncthing"])
    # Set API key
    if st_key:
        run_command(["syncthing", "cli", "config", "gui", "apikey", "set", st_key])

    # Add device
    if st_pixel_id:
        run_command(
            [
                "syncthing",
                "cli",
                "config",
                "devices",
                "add",
                "--device-id",
                st_pixel_id,
                "--name",
                "Pixel",
            ]
        )

    # Add folder
    if st_folder_id:
        run_command(
            [
                "syncthing",
                "cli",
                "config",
                "folders",
                "add",
                "--id",
                st_folder_id,
                "--path",
                sync_dir,
            ]
        )

        # Add device to folder
        if st_pixel_id:
            run_command(
                [
                    "syncthing",
                    "cli",
                    "config",
                    "folders",
                    st_folder_id,
                    "devices",
                    "add",
                    "--device-id",
                    st_pixel_id,
                ]
            )

    # Restart Syncthing
    run_command(["syncthing", "cli", "system", "restart"])
    time.sleep(5)


def setup_syncthing() -> None:
    try:
        setup_syncthing_config()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
