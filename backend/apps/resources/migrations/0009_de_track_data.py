import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def de_track_resources(apps, schema_editor):
    """Strip track targeting ahead of the track-column removal.

    - Role-less audience rows (track-only) are deleted so the new
      "role required" check constraint can be added.
    - Surviving (resource, role) audiences are deduped: the same role could
      previously repeat across tracks, so once the track column drops those
      rows collapse to duplicates that would violate the new
      unique_resource_role_audience constraint (0010). Keep the lowest id.
    - Track-scoped resources fall back to public visibility.
    """
    ResourceAudience = apps.get_model("resources", "ResourceAudience")
    Resources = apps.get_model("resources", "Resources")

    deleted, _ = ResourceAudience.objects.filter(role__isnull=True).delete()

    seen = set()
    dupe_ids = []
    for aud in (
        ResourceAudience.objects.order_by("id").values("id", "resource_id", "role_id")
    ):
        key = (aud["resource_id"], aud["role_id"])
        if key in seen:
            dupe_ids.append(aud["id"])
        else:
            seen.add(key)
    deduped = 0
    if dupe_ids:
        deduped, _ = ResourceAudience.objects.filter(id__in=dupe_ids).delete()

    to_public = Resources.objects.filter(visibility_scope="track").update(
        visibility_scope="public"
    )

    if deleted or deduped or to_public:
        logger.info(
            "de_track_resources: deleted %s track audiences; deduped %s "
            "cross-track role audiences; %s track→public",
            deleted, deduped, to_public,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0008_add_attachment_resource_kind"),
    ]

    operations = [
        migrations.RunPython(de_track_resources, migrations.RunPython.noop),
    ]
