import uuid
from django.db import migrations, models


def gen_sids(apps, schema_editor):
    Sessions = apps.get_model("user_sessions", "Sessions")
    for row in Sessions.objects.filter(sid__isnull=True):
        row.sid = uuid.uuid4()
        row.save(update_fields=["sid"])


class Migration(migrations.Migration):

    dependencies = [
        # replace "000X_previous" with the actual last migration in user_sessions
        ("user_sessions", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessions",
            name="sid",
            field=models.UUIDField(default=uuid.uuid4, unique=True, db_index=True),
        ),
        migrations.RunPython(gen_sids, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sessions",
            name="sid",
            field=models.UUIDField(unique=True, db_index=True),
        ),
    ]
