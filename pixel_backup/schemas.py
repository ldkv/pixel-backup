from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from django_bolt.serializers import Serializer, field_validator


class GlobalConfigIn(Serializer):
    syncthing_dir: Path | None = None
    phone_limit_gb: float | None = None
    stop_threshold_mb: int | None = None
    cron_schedule: str | None = None
    cron_timezone: ZoneInfo | None = None
    min_sleep_seconds: int | None = None
    discord_webhook_url: str | None = None

    @field_validator("cron_timezone")
    def validate_timezone(cls, value: str | None) -> ZoneInfo | None:
        if value is None:
            return None
        try:
            return ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"cron_timezone is not a valid timezone: {value!r}") from e

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if not croniter.is_valid(value):
            raise ValueError(f"cron_schedule is not a valid cron expression: {value!r}")

        return value
