import logging

from django.db import migrations, models
from django.db.models import Q

logger = logging.getLogger(__name__)


def dedupe_group_names(apps, schema_editor):
    """Make active group names globally unique before the per-track constraint
    is replaced with a global one.

    Group names were only unique *within a track*; collapsing to a global
    constraint can collide. Lowest id keeps the name; each collider is renamed
    with its (soon-to-be-removed) track name, then a numeric suffix until
    unique. Renames only ever increase uniqueness, so the old per-track
    constraint is never violated mid-migration.
    """
    Groups = apps.get_model("groups", "Groups")

    active = Groups.objects.filter(deleted_at__isnull=True).order_by("id")
    seen = set()
    renamed = 0
    for group in active:
        name = group.group_name
        if name not in seen:
            seen.add(name)
            continue
        track_name = getattr(getattr(group, "track", None), "track_name", None)
        base = f"{name} ({track_name})" if track_name else name
        candidate = base
        n = 2
        while candidate in seen:
            candidate = f"{base} {n}"
            n += 1
        group.group_name = candidate
        group.save(update_fields=["group_name"])
        seen.add(candidate)
        renamed += 1

    if renamed:
        logger.info("dedupe_group_names: renamed %s duplicate active group names", renamed)


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0004_tracks_is_archived"),
    ]

    operations = [
        migrations.RunPython(dedupe_group_names, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="groups",
            name="unique_active_group_name_per_track",
        ),
        migrations.AddConstraint(
            model_name="groups",
            constraint=models.UniqueConstraint(
                condition=Q(deleted_at__isnull=True),
                fields=("group_name",),
                name="unique_active_group_name",
            ),
        ),
        migrations.RemoveIndex(
            model_name="groups",
            name="groups_track_i_093220_idx",
        ),
        migrations.RemoveField(
            model_name="groups",
            name="track",
        ),
    ]
