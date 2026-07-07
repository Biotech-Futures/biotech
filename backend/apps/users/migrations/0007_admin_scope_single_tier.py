from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_demote_track_admins"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="adminscope",
            name="unique_admin_scope_per_track",
        ),
        migrations.RemoveConstraint(
            model_name="adminscope",
            name="unique_global_admin_scope",
        ),
        migrations.RemoveConstraint(
            model_name="adminscope",
            name="admin_scope_global_or_track",
        ),
        migrations.RemoveIndex(
            model_name="adminscope",
            name="admin_scope_track_i_594c81_idx",
        ),
        migrations.RemoveField(
            model_name="adminscope",
            name="track",
        ),
        migrations.RemoveField(
            model_name="adminscope",
            name="is_global",
        ),
        migrations.AddConstraint(
            model_name="adminscope",
            constraint=models.UniqueConstraint(fields=["user"], name="unique_admin_scope_per_user"),
        ),
        migrations.RemoveField(
            model_name="adminprofile",
            name="tracks",
        ),
    ]
