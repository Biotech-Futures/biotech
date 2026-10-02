import apps.management.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

MODELS = ["certificatesrelease", "emailsendrun", "finalistemailsettings", "finalistslides", "gradingsettings", "marksrelease", "nonfinalistemail", "nonsubmissionemail", "presentationavailability", "presentationslot", "resultsemailsettings", "resultssupervisoremail", "resultsteamemail"]


def _relabel(apps, old: str, new: str) -> None:
    """Move the models' content types, so admin history and permissions
    stay with them."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model in MODELS:
        if not ContentType.objects.filter(app_label=new, model=model).exists():
            ContentType.objects.filter(app_label=old, model=model).update(app_label=new)
    ContentType.objects.clear_cache()


def move_content_types(apps, schema_editor):
    _relabel(apps, "grading", "management")


def move_content_types_back(apps, schema_editor):
    _relabel(apps, "management", "grading")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('grading', '0023_presentation_availability_one_per_team'),
        ('groups', '0011_presentation_availability'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # The tables are the ones grading's migrations made (up to its 0023):
        # only Django's record of the models moves, so no data does.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='FinalistEmailSettings',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('symposium_date', models.DateField(blank=True, null=True)),
                        ('confirm_by', models.DateField(blank=True, null=True)),
                        ('slides_due', models.DateField(blank=True, null=True)),
                        ('registration_url', models.URLField(blank=True, max_length=500)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'db_table': 'finalist_email_settings',
                    },
                ),
                migrations.CreateModel(
                    name='GradingSettings',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('director_1_name', models.CharField(blank=True, max_length=255)),
                        ('director_1_position', models.CharField(blank=True, max_length=255)),
                        ('director_1_signature', models.FileField(blank=True, null=True, upload_to='grading/signatures/')),
                        ('director_2_name', models.CharField(blank=True, max_length=255)),
                        ('director_2_position', models.CharField(blank=True, max_length=255)),
                        ('director_2_signature', models.FileField(blank=True, null=True, upload_to='grading/signatures/')),
                        ('marks_summary_template', models.FileField(blank=True, null=True, upload_to=apps.management.models.template_upload_to)),
                        ('certificate_template', models.FileField(blank=True, null=True, upload_to=apps.management.models.template_upload_to)),
                        ('mentor_certificate_template', models.FileField(blank=True, null=True, upload_to=apps.management.models.template_upload_to)),
                        ('component_weights', models.JSONField(blank=True, default=dict)),
                    ],
                    options={
                        'db_table': 'grading_settings',
                    },
                ),
                migrations.CreateModel(
                    name='ResultsEmailSettings',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('survey_url', models.URLField(blank=True, max_length=500)),
                        ('survey_closes', models.DateField(blank=True, null=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'db_table': 'results_email_settings',
                    },
                ),
                migrations.CreateModel(
                    name='CertificatesRelease',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('released_at', models.DateTimeField(blank=True, null=True)),
                        ('exclude_finalists', models.BooleanField(default=True)),
                        ('released_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificates_releases', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'certificates_release',
                    },
                ),
                migrations.CreateModel(
                    name='EmailSendRun',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('key', models.CharField(max_length=64, unique=True)),
                        ('held_until', models.DateTimeField(blank=True, null=True)),
                        ('started_at', models.DateTimeField(blank=True, null=True)),
                        ('finished_at', models.DateTimeField(blank=True, null=True)),
                        ('due', models.PositiveIntegerField(default=0)),
                        ('emailed', models.PositiveIntegerField(default=0)),
                        ('failed', models.PositiveIntegerField(default=0)),
                        ('error', models.CharField(blank=True, max_length=300)),
                        ('missed', models.JSONField(blank=True, default=list)),
                        ('started_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'email_send_run',
                    },
                ),
                migrations.CreateModel(
                    name='FinalistSlides',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('file', models.JSONField()),
                        ('submitted_at', models.DateTimeField()),
                        ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='finalist_slides', to='groups.groups')),
                        ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finalist_slides', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'finalist_slides',
                    },
                ),
                migrations.CreateModel(
                    name='MarksRelease',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('released_at', models.DateTimeField(blank=True, null=True)),
                        ('released_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marks_releases', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'marks_release',
                    },
                ),
                migrations.CreateModel(
                    name='NonFinalistEmail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('sent_at', models.DateTimeField(auto_now_add=True)),
                        ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='nonfinalist_email', to='groups.groups')),
                        ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'nonfinalist_email',
                    },
                ),
                migrations.CreateModel(
                    name='NonSubmissionEmail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('sent_at', models.DateTimeField(auto_now_add=True)),
                        ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='nonsubmission_email', to='groups.groups')),
                        ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'nonsubmission_email',
                    },
                ),
                migrations.CreateModel(
                    name='PresentationSlot',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('year', models.PositiveSmallIntegerField()),
                        ('starts_at', models.TimeField()),
                        ('ends_at', models.TimeField()),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        'db_table': 'presentation_slot',
                        'ordering': ['year', 'starts_at', 'ends_at'],
                        'constraints': [models.UniqueConstraint(fields=('year', 'starts_at', 'ends_at'), name='uniq_presentation_slot_per_year'), models.CheckConstraint(condition=models.Q(('ends_at__gt', models.F('starts_at'))), name='presentation_slot_ends_after_it_starts')],
                    },
                ),
                migrations.CreateModel(
                    name='PresentationAvailability',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('submitted_at', models.DateTimeField(blank=True, null=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='presentation_availability', to='groups.groups')),
                        ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                        ('slots', models.ManyToManyField(blank=True, related_name='available', to='management.presentationslot')),
                    ],
                    options={
                        'db_table': 'presentation_availability',
                    },
                ),
                migrations.CreateModel(
                    name='ResultsTeamEmail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('sent_at', models.DateTimeField(auto_now_add=True)),
                        ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='results_email', to='groups.groups')),
                        ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'results_team_email',
                    },
                ),
                migrations.CreateModel(
                    name='ResultsSupervisorEmail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('year', models.PositiveSmallIntegerField()),
                        ('sent_at', models.DateTimeField(auto_now_add=True)),
                        ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                        ('supervisor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'results_supervisor_email',
                        'constraints': [models.UniqueConstraint(fields=('supervisor', 'year'), name='unique_results_email_per_supervisor_year')],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(move_content_types, move_content_types_back),
    ]
