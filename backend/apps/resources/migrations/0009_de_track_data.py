import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def de_track_resources(apps, schema_editor):
    """Strip track targeting ahead of the track-column removal.

    - Role-less audience rows (track-only) are deleted so the new
      "role required" check constraint can be added.
    - Track-scoped resources fall back to public visibility.
    """
    Resources = apps.get_model("resources", "Resources")
    ResourceAudience = apps.get_model("resources", "ResourceAudience")

    deleted, _ = ResourceAudience.objects.filter(role__isnull=True).delete()
    to_public = Resources.objects.filter(visibility_scope="track").update(
        visibility_scope="public"
    )

    if deleted or to_public:
        logger.info(
            "de_track_resources: deleted %s track audiences; %s track→public",
            deleted, to_public,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0008_add_attachment_resource_kind"),
    ]

    operations = [
        migrations.RunPython(de_track_resources, migrations.RunPython.noop),
    ]
