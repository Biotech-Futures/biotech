from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_user_state"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="user",
            name="users_track_i_1a6677_idx",
        ),
        migrations.RemoveField(
            model_name="user",
            name="track",
        ),
    ]
