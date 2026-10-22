import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    """Known universities get a full name (the old name, so existing rows
    keep their text), an acronym and a country, both optional and not
    unique."""

    dependencies = [
        ('users', '0035_merge_0033_mentor_weekly_hours_0034_email_check_job'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='knownuniversity',
            name='known_university_name_unique',
        ),
        migrations.RenameField(
            model_name='knownuniversity',
            old_name='name',
            new_name='full_name',
        ),
        migrations.AddField(
            model_name='knownuniversity',
            name='acronym',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='knownuniversity',
            name='country',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterModelOptions(
            name='knownuniversity',
            options={
                'ordering': ['full_name'],
                'verbose_name': 'Known University',
                'verbose_name_plural': 'Known Universities',
            },
        ),
        migrations.AddConstraint(
            model_name='knownuniversity',
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower('full_name'), name='known_university_full_name_unique',
            ),
        ),
        migrations.AddIndex(
            model_name='knownuniversity',
            index=models.Index(django.db.models.functions.text.Lower('acronym'), name='known_university_acronym_lower'),
        ),
    ]
