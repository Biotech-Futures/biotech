import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def delete_track_tasks(apps, schema_editor):
    """Hard-delete TRACK-type tasks (Task.parent CASCADE removes descendants)
    and remap the retired track_admin creator role to global_admin.

    NOTE: this migration only DROPS the old check constraint and does the data
    work. The column/field removal lives in 0011 so the cascade DELETE here
    commits first — Postgres refuses to ALTER a table that still has pending
    (deferred) FK trigger events from a cascade delete in the same transaction
    ("cannot ALTER TABLE ... because it has pending trigger events").
    """
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
    ]
