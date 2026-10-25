import apps.users.models.student_profile
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import OuterRef, Subquery
from django.db.models.functions import ExtractYear


def year_registered(apps, schema_editor):
    """Each student's challenge year so far: the year their account was made,
    as the guardian and supervisor emails counted them before."""
    StudentProfile = apps.get_model("users", "StudentProfile")
    User = apps.get_model("users", "User")
    joined = User.objects.filter(pk=OuterRef("user_id")).annotate(year=ExtractYear("date_joined")).values("year")
    StudentProfile.objects.update(challenge_year=Subquery(joined[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0042_registration_window_closed_until_set'),
    ]

    operations = [
        # The database gets a plain value: the default works out the challenge
        # year, which reads tables another app may not have made yet.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='studentprofile',
                    name='challenge_year',
                    field=models.PositiveSmallIntegerField(default=2026),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='studentprofile',
                    name='challenge_year',
                    field=models.PositiveSmallIntegerField(
                        default=apps.users.models.student_profile.default_challenge_year,
                    ),
                ),
            ],
        ),
        migrations.RunPython(year_registered, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='studentprofile',
            index=models.Index(fields=['challenge_year'], name='student_pro_challen_2fa759_idx'),
        ),
        migrations.AlterField(
            model_name='registrationstudent',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='registrationsubmission',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='registrationsubmission',
            constraint=models.UniqueConstraint(fields=('window', 'student'), name='registration_once_per_window'),
        ),
    ]
