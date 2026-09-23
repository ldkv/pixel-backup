from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from django_bolt.serializers import Serializer, field, field_validator


class GlobalConfigSchema(Serializer):
    syncthing_dir: str | None = None
    phone_limit_gb: float | None = None
    stop_threshold_mb: int | None = None
    cron_schedule: str | None = None
    cron_timezone: str | None = None
    min_sleep_seconds: int | None = None
    discord_webhook_url: str | None = None

    @field_validator("cron_timezone")
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"cron_timezone is not a valid timezone: {value!r}") from e

        return value

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if not croniter.is_valid(value):
            raise ValueError(f"cron_schedule is not a valid cron expression: {value!r}")

        return value


class UserConfigIn(Serializer):
    username: str
    source_dir: str
    sync_order: int


class UserConfigOut(Serializer):
    id: int
    username: str
    source_dir: str
    sync_order: int
    sync_cutoff_at: datetime
    last_timestamp_ns: int


class BatchOut(Serializer):
    id: int
    files_count: int
    total_bytes: int
    synced_at: datetime
    username: str = field(source="user_config.username")


class SyncOut(Serializer):
    started: bool
