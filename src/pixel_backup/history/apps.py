from django.apps import AppConfig


class HistoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pixel_backup.history"
    label = "history"
    verbose_name = "Sync History"
