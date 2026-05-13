from django.db import migrations, models


def backfill_reminder_stamps(apps, schema_editor):
    # Map each prior `True` bool to start_datetime so the don't-re-spam
    # invariant survives the field swap.
    Events = apps.get_model("events", "Events")
    for event in Events.objects.filter(reminder_sent=True):
        Events.objects.filter(pk=event.pk).update(
            reminder_24h_sent_for_start=event.start_datetime
        )
    for event in Events.objects.filter(reminder_1h_sent=True):
        Events.objects.filter(pk=event.pk).update(
            reminder_1h_sent_for_start=event.start_datetime
        )


def reverse_backfill(apps, schema_editor):
    Events = apps.get_model("events", "Events")
    Events.objects.filter(reminder_24h_sent_for_start__isnull=False).update(
        reminder_sent=True
    )
    Events.objects.filter(reminder_1h_sent_for_start__isnull=False).update(
        reminder_1h_sent=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0008_add_reminder_1h_sent_to_events"),
    ]

    operations = [
        migrations.AddField(
            model_name="events",
            name="reminder_24h_sent_for_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="events",
            name="reminder_1h_sent_for_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_reminder_stamps, reverse_backfill),
        migrations.RemoveField(model_name="events", name="reminder_sent"),
        migrations.RemoveField(model_name="events", name="reminder_1h_sent"),
    ]
