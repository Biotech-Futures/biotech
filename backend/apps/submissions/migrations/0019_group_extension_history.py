from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0001_initial"),
        ("submissions", "0018_group_extension_revoked"),
    ]

    operations = [
        # One row per group ever -> many rows (revoked history kept), with
        # at most one ACTIVE extension per group.
        migrations.AlterField(
            model_name="groupextension",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="submission_extensions",
                to="groups.groups",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupextension",
            constraint=models.UniqueConstraint(
                condition=models.Q(("revoked_at__isnull", True)),
                fields=("group",),
                name="uniq_active_extension_per_group",
            ),
        ),
    ]
