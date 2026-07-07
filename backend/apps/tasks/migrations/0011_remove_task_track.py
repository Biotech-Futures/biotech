from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema half of the track removal for Task.

    Split out from 0010 so the cascade DELETE / role remap in 0010 commits
    first. On Postgres the deferred FK trigger events queued by that cascade
    delete make an in-transaction ALTER TABLE fail with
    "cannot ALTER TABLE ... because it has pending trigger events".
    Running the column drop and field/constraint changes in this separate
    migration flushes those triggers at 0010's commit boundary.
    """

    dependencies = [
        ('tasks', '0010_delete_track_tasks'),
    ]

    operations = [
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
