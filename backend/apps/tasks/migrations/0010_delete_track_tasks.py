import logging

from django.conf import settings
from django.db import migrations, models

logger = logging.getLogger(__name__)


def delete_track_tasks(apps, schema_editor):
    """Hard-delete TRACK-type tasks (Task.parent CASCADE removes descendants)
    and remap the retired track_admin creator role to global_admin."""
    Task = apps.get_model("tasks", "Task")

    deleted, _ = Task.objects.filter(task_type="track").delete()
    remapped = Task.objects.filter(creator_role="track_admin").update(
        creator_role="global_admin"
    )

    if deleted or remapped:
        logger.info(
            "delete_track_tasks: deleted %s track tasks (+ descendants); "
            "remapped %s track_admin→global_admin",
            deleted, remapped,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0004_tracks_is_archived'),
        ('tasks', '0009_alter_task_track_to_protect'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='task',
            name='task_type_target_consistency',
        ),
        migrations.RunPython(delete_track_tasks, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='task',
            name='track',
        ),
        migrations.AlterField(
            model_name='task',
            name='creator_role',
            field=models.CharField(choices=[('global_admin', 'Administrator'), ('mentor', 'Mentor'), ('supervisor', 'Supervisor'), ('student', 'Student')], max_length=20),
        ),
        migrations.AlterField(
            model_name='task',
            name='task_type',
            field=models.CharField(choices=[('group', 'Group'), ('individual', 'Individual')], max_length=20),
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('task_type', 'group'), ('group__isnull', False), ('assigned_user__isnull', True)), models.Q(('task_type', 'individual'), ('assigned_user__isnull', False), ('group__isnull', True)), _connector='OR'), name='task_type_target_consistency'),
        ),
    ]
