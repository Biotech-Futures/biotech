"""Add slides fields (slides_mime_type, slides_file_size, slides_storage_key) to Resources (RS1)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0012_seed_recorded_session_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="resources",
            name="slides_mime_type",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="resources",
            name="slides_file_size",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resources",
            name="slides_storage_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
