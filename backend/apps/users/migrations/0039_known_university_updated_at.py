from django.db import migrations, models
import django.utils.timezone


def from_added(apps, schema_editor):
    """Each university listed already was last updated when it was added."""
    KnownUniversity = apps.get_model('users', 'KnownUniversity')
    KnownUniversity.objects.update(updated_at=models.F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0038_merge_20261021_0516'),
    ]

    operations = [
        migrations.AddField(
            model_name='knownuniversity',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RunPython(from_added, migrations.RunPython.noop),
    ]
