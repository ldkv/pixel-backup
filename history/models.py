from datetime import UTC, datetime
from functools import cached_property
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from pixel_backup.env import DEFAULT_BATCHES_CUTOFF, MEGABYTE, NANOSECONDS
from pixel_backup.schemas import GlobalConfigSchema


class ModelBase(models.Model):
    class Meta:
        abstract = True

    if TYPE_CHECKING:
        id: int


class GlobalConfig(ModelBase):
    syncthing_dir = models.CharField(default="")
    phone_limit_gb = models.FloatField(default=19.0)
    stop_threshold_mb = models.PositiveSmallIntegerField(default=5)
    cron_schedule = models.CharField(default="0 0 * * *")
    cron_timezone = models.CharField(default="UTC")
    min_sleep_seconds = models.IntegerField(default=60)
    discord_webhook_url = models.CharField(null=True, blank=True)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.cron_timezone)

    @cached_property
    def stop_threshold_bytes(self) -> int:
        return int(self.stop_threshold_mb * MEGABYTE)

    def clean(self) -> None:
        GlobalConfigSchema.from_model(self)

    @classmethod
    async def load(cls) -> GlobalConfig:
        return await cls.objects.aget()


class UserConfig(ModelBase):
    username = models.CharField(unique=True)
    source_dir = models.CharField()
    sync_order = models.PositiveSmallIntegerField(unique=True)
    sync_cutoff_ns = models.PositiveBigIntegerField(
        default=0,
        help_text="Only sync assets modified on or after this nanosecond timestamp. Advanced after each sync.",
    )

    @classmethod
    def load(cls) -> QuerySet[UserConfig]:
        return cls.objects.all().order_by("sync_order", "username")

    @property
    def sync_cutoff_at(self) -> datetime:
        """Cutoff - in datetime form."""
        return datetime.fromtimestamp(self.sync_cutoff_ns / NANOSECONDS, tz=UTC)

    @sync_cutoff_at.setter
    def sync_cutoff_at(self, value: datetime) -> None:
        self.sync_cutoff_ns = max(0, int(value.timestamp() * NANOSECONDS))

    def update_timestamp(self, new_timestamp_ns: int) -> None:
        self.sync_cutoff_ns = new_timestamp_ns
        self.save(update_fields=["sync_cutoff_ns"])


class Batch(ModelBase):
    user_config: UserConfig = models.ForeignKey(UserConfig, on_delete=models.CASCADE, related_name="batches")  # ty: ignore[invalid-assignment]
    files_count = models.PositiveIntegerField(default=0)
    total_bytes = models.PositiveBigIntegerField(default=0)
    synced_at = models.DateTimeField(default=timezone.now)
    resynced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Batches"

    if TYPE_CHECKING:
        user_config_id: int
        assets: models.QuerySet[SyncedAsset]


class SyncedAsset(ModelBase):
    user_config: UserConfig = models.ForeignKey(UserConfig, on_delete=models.CASCADE, related_name="assets")  # ty: ignore[invalid-assignment]
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    source_path = models.TextField()
    dest_path = models.TextField()
    size_bytes = models.PositiveBigIntegerField()
    created_at_ns = models.BigIntegerField()

    if TYPE_CHECKING:
        user_config_id: int
        batch_id: int

    def __gt__(self, other: "SyncedAsset") -> bool:
        return self.created_at_ns > other.created_at_ns

    @classmethod
    def get_synced_assets(cls, user_config: UserConfig, batches_ago: int = DEFAULT_BATCHES_CUTOFF) -> set[str]:
        recent_batch_ids = list(
            Batch.objects.filter(user_config=user_config).order_by("-id").values_list("id", flat=True)[:batches_ago]
        )
        batch_filter = models.Q(user_config=user_config)
        if len(recent_batch_ids) == batches_ago:
            batch_filter &= models.Q(batch_id__in=recent_batch_ids)

        return set(SyncedAsset.objects.filter(batch_filter).values_list("source_path", flat=True))
