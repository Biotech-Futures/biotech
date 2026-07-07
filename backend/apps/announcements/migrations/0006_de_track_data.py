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

    # Dedupe surviving role audiences (group NULL): the same role could
    # previously repeat across tracks, so once the track column drops (0007)
    # those rows collapse to duplicates that would violate the new
    # unique_announcement_role_audience constraint. Keep the lowest id.
    seen = set()
    dupe_ids = []
    for aud in (
        AnnouncementAudience.objects.filter(role__isnull=False, group__isnull=True)
        .order_by("id")
        .values("id", "announcement_id", "role_id")
    ):
        key = (aud["announcement_id"], aud["role_id"])
        if key in seen:
            dupe_ids.append(aud["id"])
        else:
            seen.add(key)
    deduped = 0
    if dupe_ids:
        deduped, _ = AnnouncementAudience.objects.filter(id__in=dupe_ids).delete()

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

    if deleted or deduped or to_global or to_role or stranded:
        logger.info(
            "de_track_announcements: deleted %s track audiences; deduped %s "
            "cross-track role audiences; remapped %s→global, %s→role_based, "
            "%s stranded→global",
            deleted, deduped, to_global, to_role, stranded,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("announcements", "0005_alter_announcement_visibility_scope"),
    ]

    operations = [
        migrations.RunPython(de_track_announcements, migrations.RunPython.noop),
    ]
