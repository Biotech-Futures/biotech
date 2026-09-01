from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0002_seed_components"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="overall_comment",
            field=models.TextField(blank=True, default=""),
        ),
    ]
