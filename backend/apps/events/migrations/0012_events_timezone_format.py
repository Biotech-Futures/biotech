from django.db import migrations, models


def forwards_copy_is_virtual_to_event_format(apps, schema_editor):
    Events = apps.get_model('events', 'Events')
    Events.objects.filter(is_virtual=True).update(event_format='virtual')


def backwards_copy_event_format_to_is_virtual(apps, schema_editor):
    Events = apps.get_model('events', 'Events')
    Events.objects.filter(event_format='virtual').update(is_virtual=True)
    Events.objects.exclude(event_format='virtual').update(is_virtual=False)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0011_eventrsvp_evrsvp_evt_stat_resp_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='events',
            name='event_timezone',
            field=models.CharField(default='UTC', max_length=50),
        ),
        migrations.AddField(
            model_name='events',
            name='event_format',
            field=models.CharField(
                choices=[
                    ('in_person', 'In-person'),
                    ('virtual', 'Virtual'),
                    ('hybrid', 'Hybrid'),
                ],
                default='in_person',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            forwards_copy_is_virtual_to_event_format,
            backwards_copy_event_format_to_is_virtual,
        ),
        migrations.RemoveConstraint(
            model_name='events',
            name='check_virtual_location_null',
        ),
        migrations.RemoveField(
            model_name='events',
            name='is_virtual',
        ),
    ]
