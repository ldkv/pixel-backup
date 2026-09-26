from django.contrib import admin
from django.http import HttpRequest

from history.models import Batch, GlobalConfig, SyncedAsset, UserConfig


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "syncthing_dir",
        "phone_limit_gb",
        "stop_threshold_mb",
        "cron_schedule",
        "cron_timezone",
        "min_sleep_seconds",
        "discord_webhook_url",
    ]


@admin.register(UserConfig)
class UserConfigAdmin(admin.ModelAdmin):
    list_display = ["id", "username", "source_dir", "sync_cutoff_at"]
    readonly_fields = ["id", "sync_cutoff_ns"]

    def get_readonly_fields(self, request: HttpRequest, obj: UserConfig | None = None) -> list[str]:
        # The cutoff is also the sync cursor: it can be set on creation, but changing it later can skip or re-sync assets.
        return ["sync_cutoff_ns"] if obj else []


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_select_related = ["user_config"]
    search_fields = ["user_config__username"]
    list_display = ["id", "user_config__username", "files_count", "total_bytes", "synced_at"]


@admin.register(SyncedAsset)
class SyncedFileAdmin(admin.ModelAdmin):
    list_select_related = ["user_config", "batch"]
    search_fields = ["user_config__username", "batch_id"]
    list_display = [
        "id",
        "user_config__username",
        "batch_id",
        "source_path",
        "dest_path",
        "size_bytes",
        "created_at_ns",
    ]
