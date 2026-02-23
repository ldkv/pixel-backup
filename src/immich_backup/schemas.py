from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, SecretStr

_SETTINGS_PATH = Path("/app/data/settings.json")
_USERS_PATH = Path("/app/data/users.json")


class Settings(BaseModel):
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

    @classmethod
    def load(cls, path: Path = _SETTINGS_PATH) -> "Settings":
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found at {path=}")

        with path.open("r") as f:
            data = f.read()

        return cls.model_validate_json(data)


class User(BaseModel):
    username: str
    immich_api_key: str
    asset_created_after: datetime = datetime(1970, 1, 1)
    last_asset_id: int = 0


class UserSync(BaseModel):
    users: list[User] = []

    @classmethod
    def load(cls, path: Path = _USERS_PATH) -> "UserSync":
        if not path.exists():
            raise FileNotFoundError(f"Users settings file not found at {path=}")

        with path.open("r") as f:
            data = f.read()

        return cls.model_validate_json(data)

    def save(self, path: Path = _USERS_PATH) -> None:
        with path.open("w") as f:
            f.write(self.model_dump_json(indent=4))


class ImmichAsset(BaseModel):
    id: int
    originalPath: str
