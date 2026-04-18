# Align groups, tracks, group membership, and group_interest with target PostgreSQL DDL.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def forwards_copy_group_soft_delete(apps, schema_editor):
    Groups = apps.get_model("groups", "Groups")
    for row in Groups.objects.all():
        if getattr(row, "deleted_flag", False):
            row.deleted_at = row.deleted_datetime or django.utils.timezone.now()
        else:
            row.deleted_at = None
        row.save(update_fields=["deleted_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0004_remove_groupmembership_unique_active_group_membership_and_more"),
        ("users", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="groups",
            name="unique_active_group_name_per_track",
        ),
        migrations.RemoveConstraint(
            model_name="groups",
            name="group_deleted_after_created",
        ),
        migrations.RemoveIndex(
            model_name="groups",
            name="groups_deleted_f0201e_idx",
        ),
        migrations.RemoveIndex(
            model_name="groups",
            name="groups_creatio_f6499a_idx",
        ),
        migrations.AddField(
            model_name="groups",
            name="year_min",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="groups",
            name="year_max",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="groups",
            name="lead_mentor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="led_groups",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="groups",
            name="max_members",
            field=models.PositiveIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="groups",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_copy_group_soft_delete, noop_reverse),
        migrations.RemoveField(
            model_name="groups",
            name="deleted_flag",
        ),
        migrations.RemoveField(
            model_name="groups",
            name="deleted_datetime",
        ),
        migrations.RenameField(
            model_name="groups",
            old_name="creation_datetime",
            new_name="created_at",
        ),
        migrations.AddIndex(
            model_name="groups",
            index=models.Index(fields=["deleted_at"], name="groups_deleted_at_idx"),
        ),
        migrations.AddIndex(
            model_name="groups",
            index=models.Index(fields=["created_at"], name="groups_created_at_idx"),
        ),
        migrations.AddConstraint(
            model_name="groups",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("track", "group_name"),
                name="unique_active_group_name_per_track",
            ),
        ),
        migrations.AddConstraint(
            model_name="groups",
            constraint=models.CheckConstraint(
                condition=models.Q(("deleted_at__isnull", True))
                | models.Q(("deleted_at__gte", models.F("created_at"))),
                name="group_deleted_after_created",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "group_members" RENAME TO "group_membership";',
                    reverse_sql='ALTER TABLE "group_membership" RENAME TO "group_members";',
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name="groupmembership",
                    table="group_membership",
                ),
            ],
        ),
        migrations.RemoveConstraint(
            model_name="groupmembership",
            name="unique_group_membership",
        ),
        migrations.AddField(
            model_name="groupmembership",
            name="joined_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="groupmembership",
            name="left_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="groupmembership",
            name="membership_role",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddIndex(
            model_name="groupmembership",
            index=models.Index(fields=["left_at"], name="group_membe_left_at_idx"),
        ),
        migrations.AddConstraint(
            model_name="groupmembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("left_at__isnull", True)),
                fields=("group", "user"),
                name="unique_active_group_membership",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupmembership",
            constraint=models.CheckConstraint(
                condition=models.Q(("left_at__gte", models.F("joined_at")), ("left_at__isnull", True), _connector="OR"),
                name="group_membership_left_after_joined",
            ),
        ),
        migrations.RenameField(
            model_name="tracks",
            old_name="track_name",
            new_name="track_code",
        ),
        migrations.CreateModel(
            name="GroupInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_interests",
                        to="groups.groups",
                    ),
                ),
                (
                    "interest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_links",
                        to="users.areasofinterest",
                    ),
                ),
            ],
            options={
                "db_table": "group_interest",
            },
        ),
        migrations.AddConstraint(
            model_name="groupinterest",
            constraint=models.UniqueConstraint(fields=("group", "interest"), name="unique_group_interest"),
        ),
        migrations.AddIndex(
            model_name="groupinterest",
            index=models.Index(fields=["group"], name="group_interest_group_idx"),
        ),
        migrations.AddIndex(
            model_name="groupinterest",
            index=models.Index(fields=["interest"], name="group_interest_interest_idx"),
        ),
    ]
