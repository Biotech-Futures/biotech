from django.db import migrations, models

# The links the fields used to start with. A saved row still holding one was
# never set by an admin, so it's cleared to be entered for this year.
OLD_REGISTRATION_URL = "https://events.humanitix.com/biotech-futures-symposium"
OLD_SURVEY_URL = "https://sydney.au1.qualtrics.com/jfe/form/SV_cCKb80Gg7IhgBpA"


def clear_old_links(apps, schema_editor):
    apps.get_model("grading", "FinalistEmailSettings").objects.filter(
        registration_url=OLD_REGISTRATION_URL
    ).update(registration_url="")
    apps.get_model("grading", "ResultsEmailSettings").objects.filter(
        survey_url=OLD_SURVEY_URL
    ).update(survey_url="")


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0014_mentor_certificate_template"),
    ]

    operations = [
        migrations.AlterField(
            model_name="finalistemailsettings",
            name="registration_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name="resultsemailsettings",
            name="survey_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.RunPython(clear_old_links, migrations.RunPython.noop),
    ]
