from django.db import models


class Batch(models.Model):
    username = models.CharField(max_length=255, db_index=True)
    synced_at = models.DateTimeField(auto_now_add=True)
    files_count = models.PositiveIntegerField()
    total_bytes = models.PositiveBigIntegerField()

    class Meta:
        db_table = "batches"


class SyncedFile(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="files")
    username = models.CharField(max_length=255)
    source_path = models.TextField()
    dest_path = models.TextField()
    size_bytes = models.PositiveBigIntegerField()
    asset_created_at_ns = models.BigIntegerField()

    class Meta:
        db_table = "synced_files"
        indexes = [models.Index(fields=["username"], name="idx_synced_files_username")]
        constraints = [
            models.UniqueConstraint(fields=["username", "source_path"], name="unique_username_source_path"),
        ]
