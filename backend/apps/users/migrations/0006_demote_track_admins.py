import logging

from django.db import migrations
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def demote_track_admins(apps, schema_editor):
    """Single-tier admin model: drop track-scoped admin grants entirely.

    Users left with no AdminScope row also get their active 'admin' role
    assignment closed, so they don't sit in a role=admin-but-403 half-state.
    """
    AdminScope = apps.get_model("users", "AdminScope")
    RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")

    track_scoped = AdminScope.objects.filter(is_global=False)
    affected_user_ids = set(track_scoped.values_list("user_id", flat=True))
    deleted, _ = track_scoped.delete()

    demoted_user_ids = [
        uid for uid in affected_user_ids
        if not AdminScope.objects.filter(user_id=uid).exists()
    ]
    now = timezone.now()
    closed = RoleAssignmentHistory.objects.filter(
        user_id__in=demoted_user_ids,
        role__role_name__iexact="admin",
        valid_from__lte=now,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).update(valid_to=now)

    if deleted or closed:
        logger.info(
            "demote_track_admins: removed %s track-scoped admin grants; "
            "closed admin role for %s fully-demoted users",
            deleted, closed,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_supervisorprofile_school_name_optional"),
        ("resources", "0008_add_attachment_resource_kind"),
    ]

    operations = [
        migrations.RunPython(demote_track_admins, migrations.RunPython.noop),
    ]
