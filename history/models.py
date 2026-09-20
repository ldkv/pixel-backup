from datetime import UTC, datetime
from functools import cached_property
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

from pixel_backup.env import DEFAULT_BATCHES_CUTOFF, NANOSECONDS


class ModelBase(models.Model):
    class Meta:
        abstract = True

    if TYPE_CHECKING:
        id: int


class UserConfig(ModelBase):
    username = models.CharField(unique=True)
    source_dir = models.CharField()
    sync_order = models.PositiveSmallIntegerField(unique=True)
    sync_cutoff_at = models.DateTimeField(
        default=datetime.min.replace(tzinfo=UTC),
        help_text="Only sync assets created on or after this date/time; earlier assets are skipped.",
    )
    last_timestamp_ns = models.PositiveBigIntegerField(default=0)

    @classmethod
    def load(cls) -> list[UserConfig]:
        return list(cls.objects.all().order_by("sync_order", "username"))

    @cached_property
    def cutoff_timestamp_ns(self) -> int:
        """Effective cursor: the later of the last synced timestamp and the configured cutoff."""
        cutoff_ns = int(self.sync_cutoff_at.timestamp() * NANOSECONDS)
        return max(self.last_timestamp_ns, cutoff_ns)

    def update_timestamp(self, new_timestamp_ns: int) -> None:
        self.last_timestamp_ns = new_timestamp_ns
        self.save(update_fields=["last_timestamp_ns"])


class Batch(ModelBase):
    user_config: UserConfig = models.ForeignKey(UserConfig, on_delete=models.CASCADE, related_name="batches")  # ty: ignore[invalid-assignment]
    files_count = models.PositiveIntegerField(default=0)
    total_bytes = models.PositiveBigIntegerField(default=0)
    synced_at = models.DateTimeField(default=timezone.now)

    if TYPE_CHECKING:
        user_config_id: int


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

    @classmethod
    def get_synced_assets(cls, user_config: UserConfig, batches_ago: int = DEFAULT_BATCHES_CUTOFF) -> set[str]:
        recent_batch_ids = list(
            Batch.objects.filter(user_config=user_config).order_by("-id").values_list("id", flat=True)[:batches_ago]
        )
        batch_filter = models.Q(user_config=user_config)
        if len(recent_batch_ids) == batches_ago:
            batch_filter &= models.Q(batch_id__in=recent_batch_ids)

        return set(SyncedAsset.objects.filter(batch_filter).values_list("source_path", flat=True))
