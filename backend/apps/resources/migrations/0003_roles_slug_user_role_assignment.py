import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0002_initial"),
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
                name="roles_slug_not_empty",
            ),
        ),
        migrations.AlterModelTable(
            name="roleassignmenthistory",
            table="user_role_assignment",
        ),
        migrations.AlterField(
            model_name="roleassignmenthistory",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_role_assignments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="roleassignmenthistory",
            name="role",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="role_assignments",
                to="resources.roles",
            ),
        ),
    ]
