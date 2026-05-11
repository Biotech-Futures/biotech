from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0006_rsvp_standard_wording"),
    ]

    operations = [
        migrations.AddField(
            model_name="events",
            name="reminder_sent",
            field=models.BooleanField(default=False),
        ),
    ]
