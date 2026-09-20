from functools import cached_property
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

DB_BULK_SIZE = 400
DEFAULT_BATCHES_CUTOFF = 7
MEGABYTE = 1024**2
GIGABYTE = MEGABYTE * 1024
NANOSECONDS = 1_000_000_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        str_strip_whitespace=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pytest_version: str = ""
    data_dir: Path = Path("./configs")
    syncthing_dir: Path = Path("/immich/syncthing")
    phone_limit_gb: float = 19.0
    stop_threshold_mb: int = 5
    cron_schedule: str = "0 0 * * *"
    timezone: ZoneInfo = ZoneInfo("UTC")
    min_sleep_seconds: int = 60
    discord_webhook_url: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_dir / "pixel_backup.db"

    @cached_property
    def stop_threshold_bytes(self) -> int:
        return int(self.stop_threshold_mb * MEGABYTE)


ENV_VARS = Settings()
