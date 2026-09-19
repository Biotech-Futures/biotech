from django.db import migrations, models


def _tick_existing_unreleased(apps, schema_editor):
    """Flip the existing singleton to the new default.

    Only rows where certificates were never released — a live release with the
    box deliberately unticked must not be overridden by a default change.
    """
    CertificatesRelease = apps.get_model("grading", "CertificatesRelease")
    CertificatesRelease.objects.filter(released_at__isnull=True).update(
        exclude_finalists=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0004_certificates_exclude_finalists"),
    ]

    operations = [
        migrations.AlterField(
            model_name="certificatesrelease",
            name="exclude_finalists",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(_tick_existing_unreleased, migrations.RunPython.noop),
    ]
