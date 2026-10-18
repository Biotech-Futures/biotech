# Generated manually because this is a small additive, backwards-compatible change.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_user_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_image_content_type",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_image_key",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
    ]
