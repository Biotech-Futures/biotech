import logging

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery

logger = logging.getLogger(__name__)


def backfill_user_state(apps, schema_editor):
    """Copy each user's region from their (soon-to-be-removed) track's state."""
    User = apps.get_model("users", "User")
    Tracks = apps.get_model("groups", "Tracks")

    updated = User.objects.filter(track__isnull=False, state__isnull=True).update(
        state=Subquery(
            Tracks.objects.filter(id=OuterRef("track_id")).values("state_id")[:1]
        )
    )
    if updated:
        logger.info("backfill_user_state: set state on %s users from track.state", updated)


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0004_tracks_is_archived"),
        ("users", "0007_admin_scope_single_tier"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="groups.countrystates",
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["state"], name="users_state_i_69ebd8_idx"),
        ),
        migrations.RunPython(backfill_user_state, migrations.RunPython.noop),
    ]
