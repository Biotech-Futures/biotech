"""Challenge Start as a date and time (starts_at) rather than a date
(starts_on): a date already set starts at 23:59 that day, Sydney time, as a
day picked on the page does."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.db import migrations, models

SYDNEY = ZoneInfo("Australia/Sydney")


def date_to_time(apps, schema_editor):
    ChallengeStart = apps.get_model("management", "ChallengeStart")
    for row in ChallengeStart.objects.exclude(starts_on=None):
        row.starts_at = datetime.combine(row.starts_on, time(23, 59), tzinfo=SYDNEY)
        row.save(update_fields=["starts_at"])


def time_to_date(apps, schema_editor):
    ChallengeStart = apps.get_model("management", "ChallengeStart")
    for row in ChallengeStart.objects.exclude(starts_at=None):
        row.starts_on = row.starts_at.astimezone(SYDNEY).date()
        row.save(update_fields=["starts_on"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0019_pages_visibility_shown_from"),
    ]

    operations = [
        migrations.AddField(
            model_name="challengestart",
            name="starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(date_to_time, time_to_date),
        migrations.RemoveField(
            model_name="challengestart",
            name="starts_on",
        ),
    ]
