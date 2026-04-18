# User.track required; student_interest.student_user_id column; areas_of_interest unique.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_fill_track(apps, schema_editor):
    Countries = apps.get_model("groups", "Countries")
    CountryStates = apps.get_model("groups", "CountryStates")
    Tracks = apps.get_model("groups", "Tracks")
    User = apps.get_model("users", "User")

    if not Tracks.objects.exists():
        country, _ = Countries.objects.get_or_create(country_name="Seed")
        state, _ = CountryStates.objects.get_or_create(country=country, state_name="Seed")
        Tracks.objects.get_or_create(track_code="GLOBAL-SEED", defaults={"state": state})

    first = Tracks.objects.order_by("id").first()
    User.objects.filter(track__isnull=True).update(track_id=first.id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
        ("groups", "0005_align_groups_track_membership_interest"),
    ]

    operations = [
        migrations.RunPython(forwards_fill_track, noop_reverse),
        migrations.AlterField(
            model_name="user",
            name="track",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="groups.tracks",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "student_interest" RENAME COLUMN "user_id" TO "student_user_id";',
                    reverse_sql='ALTER TABLE "student_interest" RENAME COLUMN "student_user_id" TO "user_id";',
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="studentinterest",
                    name="user",
                    field=models.ForeignKey(
                        db_column="student_user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="areasofinterest",
            constraint=models.UniqueConstraint(fields=("interest_desc",), name="areas_of_interest_interest_desc_uniq"),
        ),
    ]
