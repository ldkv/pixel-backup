import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, field_validator

from pixel_backup.settings import ENV_VARS

logger = logging.getLogger(__name__)


class ConfigBase(BaseModel):
    path: ClassVar[Path]

    @classmethod
    def load(cls, path: Path | None = None, generate_default: bool = False) -> Self:
        cls.path = path or cls.path
        if cls.path.exists():
            with cls.path.open("r") as f:
                data = f.read()

            return cls.model_validate_json(data)

        if not generate_default:
            raise FileNotFoundError(f"Config file not found at {cls.path=}.")

        logger.warning(f"Config file not found at {cls.path=}. Generate default config.")
        configs = cls.model_construct()
        configs.save()
        return configs

    def save(self, path: Path | None = None) -> None:
        target_path = path or self.path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w") as f:
            f.write(self.model_dump_json(indent=4))


class User(BaseModel):
    username: str
    source_dir: Path
    asset_created_after: datetime = datetime(1970, 1, 1, tzinfo=UTC)
    last_timestamp_ns: int = 0

    @field_validator("asset_created_after", mode="after")
    def ensure_utc(cls, dt: datetime) -> datetime:
        """Always use UTC to ensure a fixed datetime reference."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)

        return dt.astimezone(UTC)

    def model_post_init(self, _):
        self.last_timestamp_ns = self.last_timestamp_ns or int(self.asset_created_after.timestamp() * 1_000_000_000)

    def update_timestamp(self, new_timestamp_ns: int) -> None:
        self.last_timestamp_ns = new_timestamp_ns
        self.asset_created_after = datetime.fromtimestamp(new_timestamp_ns / 1_000_000_000, tz=UTC)


class UserConfig(ConfigBase):
    path: ClassVar[Path] = ENV_VARS.user_configs

    users: list[User] = []
