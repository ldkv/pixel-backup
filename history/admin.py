from django.contrib import admin

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
