# The finalist announcement becomes one row per outcome email (finalist,
# non-finalist, non-submission, and the results emails to groups and to
# supervisors). Its one row, if there is one, is the finalist email's.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0006_finalist_announcement'),
    ]

    operations = [
        migrations.RenameModel('FinalistAnnouncement', 'OutcomeAnnouncement'),
        migrations.AlterModelTable('outcomeannouncement', 'outcome_announcement'),
        migrations.AddField(
            model_name='outcomeannouncement',
            name='key',
            field=models.CharField(default='finalists', max_length=32, unique=True),
            preserve_default=False,
        ),
    ]
