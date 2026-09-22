from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("submissions", "0017_group_extension_grace_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupextension",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="groupextension",
            name="revoked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="revoked_submission_extensions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
