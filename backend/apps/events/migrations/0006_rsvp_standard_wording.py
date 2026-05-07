"""Rename RSVP enum to meeting-standard wording.

going  -> accepted
maybe  -> tentative

Drops the old check constraint, remaps existing rows in-place, alters
the field choices, and re-adds the constraint with the new values.
"""

from django.db import migrations, models


def forwards(apps, schema_editor):
    EventRsvp = apps.get_model("events", "EventRsvp")
    EventRsvp.objects.filter(rsvp_status="going").update(rsvp_status="accepted")
    EventRsvp.objects.filter(rsvp_status="maybe").update(rsvp_status="tentative")


def backwards(apps, schema_editor):
    EventRsvp = apps.get_model("events", "EventRsvp")
    EventRsvp.objects.filter(rsvp_status="accepted").update(rsvp_status="going")
    EventRsvp.objects.filter(rsvp_status="tentative").update(rsvp_status="maybe")


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0005_events_location_link"),
    ]

    operations = [
        # Drop the old constraint before remapping data, otherwise the
        # UPDATE could transiently violate it on engines that re-check
        # per-row.
        migrations.RemoveConstraint(
            model_name="eventrsvp",
            name="event_rsvp_response_state_valid",
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="eventrsvp",
            name="rsvp_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("accepted", "Accepted"),
                    ("tentative", "Tentative"),
                    ("declined", "Declined"),
                ],
                default="pending",
                max_length=50,
            ),
        ),
        migrations.AddConstraint(
            model_name="eventrsvp",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("responded_at__isnull", True),
                    ("rsvp_status__in", ["accepted", "tentative", "declined"]),
                    _connector="OR",
                ),
                name="event_rsvp_response_state_valid",
            ),
        ),
    ]