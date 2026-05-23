import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_tracks_is_archived'),
        ('tasks', '0007_rename_assigned_student_to_assigned_user'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='task',
            name='task_type_target_consistency',
        ),
        migrations.AddField(
            model_name='task',
            name='track',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='track_tasks',
                to='groups.tracks',
            ),
        ),
        migrations.AlterField(
            model_name='task',
            name='task_type',
            field=models.CharField(
                choices=[
                    ('group', 'Group'),
                    ('individual', 'Individual'),
                    ('track', 'Track'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ('task_type', 'group'),
                        ('group__isnull', False),
                        ('assigned_user__isnull', True),
                        ('track__isnull', True),
                    ),
                    models.Q(
                        ('task_type', 'individual'),
                        ('assigned_user__isnull', False),
                        ('group__isnull', True),
                        ('track__isnull', True),
                    ),
                    models.Q(
                        ('task_type', 'track'),
                        ('track__isnull', False),
                        ('group__isnull', True),
                        ('assigned_user__isnull', True),
                    ),
                    _connector='OR',
                ),
                name='task_type_target_consistency',
            ),
        ),
    ]
