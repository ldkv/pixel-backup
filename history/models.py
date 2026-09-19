from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django.db import models


class ModelBase(models.Model):
    class Meta:
        abstract = True

    if TYPE_CHECKING:
        id: int


class UserConfig(ModelBase):
    username = models.CharField(unique=True)
    source_dir = models.CharField()
    sync_cutoff_at = models.DateTimeField(
        default=datetime.min.replace(tzinfo=UTC),
        help_text="Only sync files created on or after this date/time; earlier files are skipped.",
    )


class Batch(ModelBase):
    user_config = models.ForeignKey(UserConfig, on_delete=models.CASCADE, related_name="batches")
    files_count = models.PositiveIntegerField()
    total_bytes = models.PositiveBigIntegerField()
    synced_at = models.DateTimeField(auto_now_add=True)

    if TYPE_CHECKING:
        id: int


class SyncedFile(ModelBase):
    user_config = models.ForeignKey(UserConfig, on_delete=models.CASCADE, related_name="files")
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="files")
    source_path = models.TextField(unique=True)
    dest_path = models.TextField()
    size_bytes = models.PositiveBigIntegerField()
    created_at_ns = models.BigIntegerField()
