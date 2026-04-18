# Align certificate tables with target PostgreSQL DDL (sql_ddl.pdf).

import django.db.models.deletion
import django.db.models.functions.datetime
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone as dj_tz


def forwards_verified_to_timestamps(apps, schema_editor):
    MentorCertificate = apps.get_model("certificates", "MentorCertificate")
    MentorCertificate.objects.filter(verified=True).update(verified_at=dj_tz.now())


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="mentorcertificate",
            name="cannot_verify_expired_certificate",
        ),
        migrations.RenameField(
            model_name="certificatetype",
            old_name="certificate_type",
            new_name="name",
        ),
        migrations.RemoveIndex(
            model_name="certificatetype",
            name="certificate_certifi_187256_idx",
        ),
        migrations.AddIndex(
            model_name="certificatetype",
            index=models.Index(fields=["name"], name="certificate_type_name_idx"),
        ),
        migrations.AddField(
            model_name="mentorcertificate",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mentorcertificate",
            name="verified_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="certificates_verified",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(forwards_verified_to_timestamps, noop_reverse),
        migrations.RemoveField(
            model_name="mentorcertificate",
            name="verified",
        ),
        migrations.AddConstraint(
            model_name="mentorcertificate",
            constraint=models.CheckConstraint(
                condition=models.Q(("expires_at__isnull", True))
                | models.Q(("expires_at__gte", django.db.models.functions.datetime.Now()))
                | models.Q(("verified_at__isnull", True)),
                name="cannot_verify_expired_certificate",
            ),
        ),
    ]
