import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_tracks_is_archived'),
        ('tasks', '0008_task_track_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='track',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='track_tasks',
                to='groups.tracks',
            ),
        ),
    ]
