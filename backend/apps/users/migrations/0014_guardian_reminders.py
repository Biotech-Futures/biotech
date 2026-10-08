from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0013_merge_20260925_0104")]
    operations = [
        migrations.AddField(model_name="studentprofile", name="guardian_reminder_sent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="studentprofile", name="guardian_reminder_due_at", field=models.DateTimeField(blank=True, null=True)),
    ]
