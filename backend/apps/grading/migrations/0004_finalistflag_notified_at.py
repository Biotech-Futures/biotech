from django.db import migrations, models


class Migration(migrations.Migration):

    # Numbered 0004 to match the sibling pdf-annotations branch (which holds
    # 0002/0003); on this branch it follows 0001 directly.
    dependencies = [
        ("grading", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="finalistflag",
            name="notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
