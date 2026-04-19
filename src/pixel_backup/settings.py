from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        str_strip_whitespace=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user_configs: Path = Path("./configs/users.json")
    syncthing_dir: Path = Path("/immich/syncthing")
    upper_limit_gb: float = 20.0
    cron_schedule: str = "0 0 * * *"
    timezone: ZoneInfo = ZoneInfo("UTC")
    min_sleep_seconds: int = 60
    discord_webhook_url: str = ""


ENV_VARS = Settings()
