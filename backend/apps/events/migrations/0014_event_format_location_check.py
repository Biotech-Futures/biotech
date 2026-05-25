from django.db import migrations, models


def clear_orphan_location_links(apps, schema_editor):
    # Legacy schema overloaded location_link as a Google Maps URL on
    # in-person events. The new constraint forbids that; clear those
    # values so the constraint applies cleanly. Same for virtual events
    # that wrongly carry a physical location.
    Events = apps.get_model("events", "Events")
    Events.objects.filter(
        event_format="in_person", location_link__isnull=False
    ).update(location_link=None)
    Events.objects.filter(
        event_format="virtual", location__isnull=False
    ).update(location=None)


def noop_reverse(apps, schema_editor):
    # We've discarded the Maps URLs; can't bring them back.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_alter_events_location_link'),
    ]

    operations = [
        migrations.RunPython(clear_orphan_location_links, noop_reverse),
        migrations.AddConstraint(
            model_name='events',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('event_format', 'in_person'), ('location_link__isnull', True)),
                    models.Q(('event_format', 'virtual'), ('location__isnull', True)),
                    ('event_format', 'hybrid'),
                    _connector='OR',
                ),
                name='check_event_format_location_consistency',
            ),
        ),
    ]
