from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0015_messagescreening")]

    operations = [
        migrations.AlterField(
            model_name="messagescreening",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("suspicious", "Suspicious"),
                    ("safe", "Safe"),
                    ("flagged", "Flagged"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
