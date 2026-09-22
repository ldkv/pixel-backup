from pathlib import Path

from pydantic import SecretStr
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
    data_dir: Path = Path("./data")
    admin_password: SecretStr = SecretStr("admin")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "pixel_backup.db"


ENV_VARS = Settings()
ENV_VARS.data_dir.mkdir(parents=True, exist_ok=True)
