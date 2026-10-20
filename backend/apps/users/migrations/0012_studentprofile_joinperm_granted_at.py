from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_user_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="joinperm_granted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
