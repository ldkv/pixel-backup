from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from pixel_backup.env import NANOSECONDS


def merge_cutoffs(apps: Apps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserConfig = apps.get_model("history", "UserConfig")
    for user_config in UserConfig.objects.all():
        user_config.sync_cutoff_ns = max(
            user_config.last_timestamp_ns,
            int(user_config.sync_cutoff_at.timestamp() * NANOSECONDS),
        )
        user_config.save(update_fields=["sync_cutoff_ns"])


class Migration(migrations.Migration):
    dependencies = [
        ("history", "0002_globalconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="userconfig",
            name="sync_cutoff_ns",
            field=models.PositiveBigIntegerField(
                default=0,
                help_text="Only sync assets modified on or after this nanosecond timestamp. Advanced after each sync.",
            ),
        ),
        migrations.RunPython(merge_cutoffs, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="userconfig",
            name="last_timestamp_ns",
        ),
        migrations.RemoveField(
            model_name="userconfig",
            name="sync_cutoff_at",
        ),
    ]
