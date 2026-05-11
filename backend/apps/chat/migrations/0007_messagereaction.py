import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0006_messages_reply_to"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("emoji", models.CharField(max_length=16)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reactions",
                        to="chat.messages",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="message_reactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Message Reaction",
                "verbose_name_plural": "Message Reactions",
                "db_table": "message_reactions",
                "unique_together": {("message", "user", "emoji")},
            },
        ),
        migrations.AddIndex(
            model_name="messagereaction",
            index=models.Index(fields=["message", "emoji"], name="message_rea_message_e_a4f1d6_idx"),
        ),
        migrations.AddIndex(
            model_name="messagereaction",
            index=models.Index(fields=["user"], name="message_rea_user_id_b9c021_idx"),
        ),
    ]
