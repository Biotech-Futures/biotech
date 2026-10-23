import apps.groups.models.groups
from django.db import migrations, models


CURRENT_YEAR = 2026


def set_existing_year(apps, schema_editor):
    Groups = apps.get_model("groups", "Groups")
    Groups.objects.update(year=CURRENT_YEAR)


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0006_delete_tracks'),
    ]

    operations = [
        # The database gets a plain value: the default works out the challenge
        # year, which reads tables another app may not have made yet.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='groups',
                    name='year',
                    field=models.PositiveSmallIntegerField(default=CURRENT_YEAR),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='groups',
                    name='year',
                    field=models.PositiveSmallIntegerField(default=apps.groups.models.groups.default_group_year),
                ),
            ],
        ),
        migrations.RunPython(
            set_existing_year,
            migrations.RunPython.noop,
        ),
    ]
