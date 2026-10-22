from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0010_supervisor_pages_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="supervisorpagessetting",
            name="registration_shown",
            field=models.BooleanField(default=True),
        ),
    ]
