import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Self

from pydantic import AwareDatetime, BaseModel

logger = logging.getLogger(__name__)

_CONFIGS_PATH = Path("./configs/")  # /app/configs in docker


class ConfigBase(BaseModel):
    path: ClassVar[Path]

    @classmethod
    def load(cls, path: Path | None = None, generate_default: bool = False) -> Self:
        target_path = path or cls.path
        if target_path.exists():
            with target_path.open("r") as f:
                data = f.read()

            return cls.model_validate_json(data)

        if not generate_default:
            raise FileNotFoundError(f"Config file not found at {target_path=}.")

        logger.warning(f"Config file not found at {target_path=}. Generate default config.")
        configs = cls()
        configs.save()
        return configs

    def save(self, path: Path | None = None) -> None:
        target_path = path or self.path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w") as f:
            f.write(self.model_dump_json(indent=4))


class Settings(ConfigBase):
    path: ClassVar[Path] = _CONFIGS_PATH / "settings.json"

    immich_library_dir: Path = Path("/immich/docker_data/library")
    syncthing_dir: Path = Path("/immich/syncthing")
    upper_limit_gb: float = 20.0
    lower_limit_gb: float = 5.0
    cron_schedule: str = "0 0 * * *"  # Default: every day at midnight
    min_sleep_seconds: int = 60


class User(BaseModel):
    username: str
    asset_created_after: AwareDatetime = datetime(1970, 1, 1, tzinfo=UTC)


class UserConfig(ConfigBase):
    path: ClassVar[Path] = _CONFIGS_PATH / "users.json"

    users: list[User] = []
