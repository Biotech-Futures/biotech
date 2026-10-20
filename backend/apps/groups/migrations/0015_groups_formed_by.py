import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def record_formers(apps, schema_editor):
    """Who formed the groups so far, where it was recorded: a registration
    (its members, or a supervisor), then an admin's creating it (the audit
    log). The first record of a group counts."""
    Groups = apps.get_model("groups", "Groups")
    RegistrationSubmission = apps.get_model("users", "RegistrationSubmission")
    AuditLog = apps.get_model("audit", "AuditLog")
    submissions = (
        RegistrationSubmission.objects.filter(group__isnull=False)
        .order_by("created_at", "pk")
        .values("group_id", "journey", "student_id", "created_by_id")
    )
    for submission in submissions:
        if submission["journey"] == "student_team":
            by, user_id = "members", submission["student_id"]
        elif submission["journey"].startswith("supervisor_"):
            by, user_id = "supervisor", submission["created_by_id"]
        else:
            continue
        Groups.objects.filter(pk=submission["group_id"], formed_by="").update(formed_by=by, created_by_id=user_id)
    created = (
        AuditLog.objects.filter(entity_type="group", action__in=["create", "bulk_create"])
        .order_by("pk")
        .values("entity_id", "actor_user_id")
    )
    for log in created:
        Groups.objects.filter(pk=log["entity_id"], formed_by="").update(
            formed_by="admin", created_by_id=log["actor_user_id"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0014_group_codes"),
        ("users", "0025_registration_multi_student"),
        ("audit", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="groups",
            name="formed_by",
            field=models.CharField(
                blank=True,
                choices=[("members", "Its members"), ("supervisor", "A supervisor"), ("admin", "An admin")],
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="groups",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(record_formers, migrations.RunPython.noop),
    ]
