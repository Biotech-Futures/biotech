from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0020_email_send_run'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailsendrun',
            name='missed',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
