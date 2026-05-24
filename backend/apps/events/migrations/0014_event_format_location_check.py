from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_alter_events_location_link'),
    ]

    operations = [
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
