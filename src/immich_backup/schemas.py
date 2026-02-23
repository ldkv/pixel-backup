import logging
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)

_CONFIGS_PATH = Path("./configs/")  # /app/configs in docker


class ConfigBase(BaseModel):
    path: ClassVar[Path]

    @classmethod
    def load(cls, generate_default: bool = False) -> Self:
        if cls.path.exists():
            with cls.path.open("r") as f:
                data = f.read()

            return cls.model_validate_json(data)

        if not generate_default:
            raise FileNotFoundError(f"Config file not found at {cls.path=}.")

        logger.warning(f"Config file not found at {cls.path=}. Generate default config.")
        configs = cls()
        configs.save()
        return configs

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            f.write(self.model_dump_json(indent=4))


class Settings(ConfigBase):
    path: ClassVar[Path] = _CONFIGS_PATH / "settings.json"

    immich_url: str = "http://localhost:2283"
    immich_timeout_seconds: int = 30
    syncthing_url: str = "http://localhost:8384"
    syncthing_key: SecretStr = SecretStr("")
    syncthing_folder_id: str = ""
    sync_dir: Path = Path("/sync")
    upper_limit_gb: float = 20.0
    lower_limit_gb: float = 5.0
    cron_schedule: str = "0 0 * * *"  # Default: every day at midnight
    min_sleep_seconds: int = 60


class User(BaseModel):
    username: str
    immich_api_key: str
    asset_created_after: datetime = datetime(1970, 1, 1)
    last_asset_id: int = 0


class UserSync(ConfigBase):
    path: ClassVar[Path] = _CONFIGS_PATH / "users.json"

    users: list[User] = []


class ImmichAsset(BaseModel):
    id: int
    originalPath: str
