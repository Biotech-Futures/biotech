import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def de_track_announcements(apps, schema_editor):
    """Strip track targeting ahead of the track-column removal.

    - Track-only audience rows (no role, no group) are deleted so the new
      "role or group required" check constraint can be added.
    - Track-based visibility scopes collapse to role_based / global.
    Group and role audiences are left untouched.
    """
    Announcement = apps.get_model("announcements", "Announcement")
    AnnouncementAudience = apps.get_model("announcements", "AnnouncementAudience")

    deleted, _ = AnnouncementAudience.objects.filter(
        role__isnull=True, group__isnull=True
    ).delete()

    to_global = Announcement.objects.filter(
        visibility_scope__in=["track", "track_based"]
    ).update(visibility_scope="global")
    to_role = Announcement.objects.filter(
        visibility_scope="track_role_based"
    ).update(visibility_scope="role_based")

    # Any announcement left "scoped" with no remaining audiences becomes global
    # so it does not strand as invisible content.
    stranded = 0
    for ann in Announcement.objects.filter(visibility_scope="scoped"):
        if not AnnouncementAudience.objects.filter(announcement_id=ann.id).exists():
            ann.visibility_scope = "global"
            ann.save(update_fields=["visibility_scope"])
            stranded += 1

    if deleted or to_global or to_role or stranded:
        logger.info(
            "de_track_announcements: deleted %s track audiences; "
            "remapped %s→global, %s→role_based, %s stranded→global",
            deleted, to_global, to_role, stranded,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("announcements", "0005_alter_announcement_visibility_scope"),
    ]

    operations = [
        migrations.RunPython(de_track_announcements, migrations.RunPython.noop),
    ]
