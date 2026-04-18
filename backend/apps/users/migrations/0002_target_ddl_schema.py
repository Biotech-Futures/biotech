# Align users / profiles with target PostgreSQL DDL (sql_ddl.pdf).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
def forwards_ensure_user_tracks(apps, schema_editor):
    User = apps.get_model("users", "User")
    Tracks = apps.get_model("groups", "Tracks")
    Countries = apps.get_model("groups", "Countries")
    CountryStates = apps.get_model("groups", "CountryStates")
    track = Tracks.objects.order_by("pk").first()
    if track is None:
        country, _ = Countries.objects.get_or_create(country_name="Default")
        state, _ = CountryStates.objects.get_or_create(
            country=country,
            state_name="Default",
        )
        track = Tracks.objects.create(track_code="GLOBAL", state=state)
    User.objects.filter(track_id__isnull=True).update(track_id=track.pk)


def forwards_fill_student_interest_profiles(apps, schema_editor):
    StudentInterest = apps.get_model("users", "StudentInterest")
    StudentProfile = apps.get_model("users", "StudentProfile")
    for si in StudentInterest.objects.all():
        uid = getattr(si, "user_id", None)
        if uid and StudentProfile.objects.filter(pk=uid).exists():
            StudentInterest.objects.filter(pk=si.pk).update(student_profile_id=uid)
        else:
            StudentInterest.objects.filter(pk=si.pk).delete()


def forwards_prune_mentor_rows(apps, schema_editor):
    MentorProfile = apps.get_model("users", "MentorProfile")
    MentorAvailability = apps.get_model("users", "MentorAvailability")
    MentorInterest = apps.get_model("users", "MentorInterest")
    MentorAvailability.objects.exclude(mentor_user_id__in=MentorProfile.objects.values_list("user_id", flat=True)).delete()
    MentorInterest.objects.exclude(mentor_user_id__in=MentorProfile.objects.values_list("user_id", flat=True)).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    # PostgreSQL: bulk UPDATE on users (forwards_ensure_user_tracks) leaves pending
    # RI/trigger events on referenced table tracks; a later AlterField on User.track
    # would ALTER tracks in the same transaction and fails with "pending trigger events".
    # Non-atomic migration commits between operations so the next step runs cleanly.
    atomic = False

    dependencies = [
        ("groups", "0005_target_ddl_schema"),
        ("users", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="studentprofile",
            old_name="has_join_permission",
            new_name="join_permission_received",
        ),
        migrations.RenameField(
            model_name="studentprofile",
            old_name="joinperm_responseID",
            new_name="join_permission_response_id",
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="year_level",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="country",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="student_profiles",
                to="groups.countries",
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="student_profiles",
                to="groups.countrystates",
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="preassigned_group",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="background",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="region",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="country",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mentor_profiles",
                to="groups.countries",
            ),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mentor_profiles",
                to="groups.countrystates",
            ),
        ),
        migrations.AlterField(
            model_name="mentorprofile",
            name="institution",
            field=models.CharField(
                blank=True,
                db_column="Institution",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="mentorprofile",
            name="mentor_reason",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="adminscope",
            name="track",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="groups.tracks",
            ),
        ),
        migrations.RunPython(forwards_ensure_user_tracks, noop_reverse),
        migrations.AlterField(
            model_name="user",
            name="track",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="groups.tracks",
            ),
        ),
        migrations.AlterField(
            model_name="areasofinterest",
            name="interest_desc",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.RemoveConstraint(
            model_name="studentinterest",
            name="pk_student_interest",
        ),
        migrations.RemoveIndex(
            model_name="studentinterest",
            name="student_int_user_id_9467fc_idx",
        ),
        migrations.AddField(
            model_name="studentinterest",
            name="student_profile",
            field=models.ForeignKey(
                db_column="student_user_id",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interests",
                to="users.studentprofile",
            ),
        ),
        migrations.RunPython(forwards_fill_student_interest_profiles, noop_reverse),
        migrations.RemoveField(
            model_name="studentinterest",
            name="user",
        ),
        migrations.AlterField(
            model_name="studentinterest",
            name="student_profile",
            field=models.ForeignKey(
                db_column="student_user_id",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interests",
                to="users.studentprofile",
            ),
        ),
        migrations.AddConstraint(
            model_name="studentinterest",
            constraint=models.UniqueConstraint(
                fields=("interest", "student_profile"),
                name="pk_student_interest",
            ),
        ),
        migrations.AddIndex(
            model_name="studentinterest",
            index=models.Index(fields=["student_profile"], name="student_int_student_idx"),
        ),
        migrations.RunPython(forwards_prune_mentor_rows, noop_reverse),
        migrations.RemoveConstraint(
            model_name="mentoravailability",
            name="unique_mentor_availability_slot",
        ),
        migrations.RemoveConstraint(
            model_name="mentoravailability",
            name="mentor_availability_weekday_valid",
        ),
        migrations.RemoveConstraint(
            model_name="mentoravailability",
            name="mentor_availability_end_after_start",
        ),
        migrations.RemoveIndex(
            model_name="mentoravailability",
            name="mentor_avai_mentor__83178e_idx",
        ),
        migrations.AlterField(
            model_name="mentoravailability",
            name="mentor_user",
            field=models.ForeignKey(
                db_column="mentor_user_id",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="availabilities",
                to="users.mentorprofile",
            ),
        ),
        migrations.RenameField(
            model_name="mentoravailability",
            old_name="mentor_user",
            new_name="mentor_profile",
        ),
        migrations.AddConstraint(
            model_name="mentoravailability",
            constraint=models.UniqueConstraint(
                fields=("mentor_profile", "weekday", "start_time", "end_time"),
                name="unique_mentor_availability_slot",
            ),
        ),
        migrations.AddConstraint(
            model_name="mentoravailability",
            constraint=models.CheckConstraint(
                condition=models.Q(("weekday__gte", 0), ("weekday__lte", 6)),
                name="mentor_availability_weekday_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="mentoravailability",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_time__gt", models.F("start_time"))),
                name="mentor_availability_end_after_start",
            ),
        ),
        migrations.AddIndex(
            model_name="mentoravailability",
            index=models.Index(fields=["mentor_profile"], name="mentor_avai_mentor_prof_idx"),
        ),
        migrations.RemoveConstraint(
            model_name="mentorinterest",
            name="unique_mentor_interest",
        ),
        migrations.RemoveIndex(
            model_name="mentorinterest",
            name="mentor_inte_mentor__6390ed_idx",
        ),
        migrations.AlterField(
            model_name="mentorinterest",
            name="mentor_user",
            field=models.ForeignKey(
                db_column="mentor_user_id",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interest_entries",
                to="users.mentorprofile",
            ),
        ),
        migrations.RenameField(
            model_name="mentorinterest",
            old_name="mentor_user",
            new_name="mentor_profile",
        ),
        migrations.AddConstraint(
            model_name="mentorinterest",
            constraint=models.UniqueConstraint(
                fields=("mentor_profile", "interest"),
                name="unique_mentor_interest",
            ),
        ),
        migrations.AddIndex(
            model_name="mentorinterest",
            index=models.Index(fields=["mentor_profile"], name="mentor_inte_mentor_prof_idx"),
        ),
    ]
