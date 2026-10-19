import logging
import os

from django.core.files.storage import default_storage
from django.db import migrations, models

logger = logging.getLogger(__name__)


def copy_signatures(apps, schema_editor):
    """Read each uploaded signature file into the database. One that can't be
    read is skipped (logged): the admin uploads it again on Document Setup.
    The old files stay where they were in storage."""
    GradingSettings = apps.get_model("management", "GradingSettings")
    for row in GradingSettings.objects.all():
        for index in (1, 2):
            field = getattr(row, f"director_{index}_signature")
            path = field.name if field else ""
            if not path:
                continue
            try:
                with default_storage.open(path, "rb") as stored:
                    image = stored.read()
            except Exception as exc:  # noqa: BLE001
                logger.warning("director signature %s not copied: %s %s", index, path, type(exc).__name__)
                continue
            setattr(row, f"director_{index}_signature_image", image)
            setattr(row, f"director_{index}_signature_name", os.path.basename(path)[:255])
        row.save()


class Migration(migrations.Migration):
    # Director signatures move from files in storage into the database.
    dependencies = [
        ("management", "0008_outcome_announcement_edited_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="gradingsettings",
            name="director_1_signature_image",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gradingsettings",
            name="director_1_signature_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="gradingsettings",
            name="director_2_signature_image",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gradingsettings",
            name="director_2_signature_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(copy_signatures, migrations.RunPython.noop),
        migrations.RemoveField(model_name="gradingsettings", name="director_1_signature"),
        migrations.RemoveField(model_name="gradingsettings", name="director_2_signature"),
    ]
