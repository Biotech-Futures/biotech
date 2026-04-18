import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_align_user_track_student_interest_areas"),
        ("groups", "0005_align_groups_track_membership_interest"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
DO $ren$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'mentor_profile' AND column_name = 'Institution'
  ) THEN
    ALTER TABLE mentor_profile RENAME COLUMN "Institution" TO institution;
  END IF;
END
$ren$;
""",
            reverse_sql="""
DO $ren$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'mentor_profile' AND column_name = 'institution'
  ) THEN
    ALTER TABLE mentor_profile RENAME COLUMN institution TO "Institution";
  END IF;
END
$ren$;
""",
        ),
        migrations.AlterField(
            model_name="mentorprofile",
            name="institution",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="mentorprofile",
            name="mentor_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="background",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="mentorprofile",
            name="region",
            field=models.CharField(blank=True, default="", max_length=80),
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
    ]
