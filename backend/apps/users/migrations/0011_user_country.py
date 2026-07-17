import logging

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery

logger = logging.getLogger(__name__)


def split_country_off_state(apps, schema_editor):
    """Give every user their own country, and drop the country-as-state mislabel.

    Registration (users/views.py) and the CSV imports used to write the country
    name into `state_name` for non-Australian registrants, because country was
    only reachable via `state.country`. Now that `User.country` exists, those
    synthetic rows are dead weight: country moves to `country`, state goes blank.
    """
    User = apps.get_model("users", "User")
    CountryStates = apps.get_model("groups", "CountryStates")

    # 1. Country was always derivable from the state row — copy it across first.
    updated = User.objects.filter(state__isnull=False).update(
        country_id=Subquery(
            CountryStates.objects.filter(id=OuterRef("state_id")).values("country_id")[:1]
        )
    )
    logger.info("user_country: set country on %s users from state.country", updated)

    # 2. Blank the states that are really countries wearing a state's name.
    synthetic_ids = [
        cs.id
        for cs in CountryStates.objects.select_related("country")
        if cs.state_name.strip().casefold() == cs.country.country_name.strip().casefold()
    ]
    if synthetic_ids:
        cleared = User.objects.filter(state_id__in=synthetic_ids).update(state=None)
        logger.info("user_country: blanked country-as-state on %s users", cleared)

    # 3. A state row only exists to be pointed at. Whatever is unreferenced now is
    #    either a country-as-state artefact or leftover seed_dummy_data/test data
    #    (the full-name rows) — there is no curated state lookup table to preserve.
    referenced = set(
        User.objects.filter(state__isnull=False).values_list("state_id", flat=True)
    )
    orphans = CountryStates.objects.exclude(id__in=referenced)
    dropped = [
        f"{cs.country.country_name}/{cs.state_name}"
        for cs in orphans.select_related("country")
    ]
    if dropped:
        orphans.delete()
        logger.info("user_country: deleted %s unreferenced states: %s",
                    len(dropped), ", ".join(sorted(dropped)))


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('groups', '0006_delete_tracks'),
        ('users', '0010_alter_mentorprofile_mentor_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='country',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='groups.countries'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['country'], name='users_country_5131e1_idx'),
        ),
        migrations.RunPython(split_country_off_state, migrations.RunPython.noop),
    ]
