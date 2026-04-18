# Align roles / user role assignment tables with target PostgreSQL DDL (sql_ddl.pdf).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_clear_null_assignments(apps, schema_editor):
    RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")
    RoleAssignmentHistory.objects.filter(user_id__isnull=True).delete()
    RoleAssignmentHistory.objects.filter(role_id__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="roles",
            name="role_name_not_empty",
        ),
        migrations.RenameField(
            model_name="roles",
            old_name="role_name",
            new_name="slug",
        ),
        migrations.AlterField(
            model_name="roles",
            name="slug",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AddConstraint(
            model_name="roles",
            constraint=models.CheckConstraint(
                condition=models.Q(("slug", ""), _negated=True),
                name="role_slug_not_empty",
            ),
        ),
        migrations.RunPython(forwards_clear_null_assignments, noop_reverse),
        migrations.AlterField(
            model_name="roleassignmenthistory",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="roleassignmenthistory",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="resources.roles",
            ),
        ),
        migrations.AlterModelTable(
            name="roleassignmenthistory",
            table="user_role_assignment",
        ),
    ]
