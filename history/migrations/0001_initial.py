import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Batch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(db_index=True, max_length=255)),
                ("synced_at", models.DateTimeField(auto_now_add=True)),
                ("files_count", models.PositiveIntegerField()),
                ("total_bytes", models.PositiveBigIntegerField()),
            ],
            options={
                "db_table": "batches",
            },
        ),
        migrations.CreateModel(
            name="SyncedFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=255)),
                ("source_path", models.TextField()),
                ("dest_path", models.TextField()),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("asset_created_at_ns", models.BigIntegerField()),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="files",
                        to="history.batch",
                    ),
                ),
            ],
            options={
                "db_table": "synced_files",
            },
        ),
        migrations.AddIndex(
            model_name="syncedfile",
            index=models.Index(fields=["username"], name="idx_synced_files_username"),
        ),
        migrations.AddConstraint(
            model_name="syncedfile",
            constraint=models.UniqueConstraint(fields=("username", "source_path"), name="unique_username_source_path"),
        ),
    ]
