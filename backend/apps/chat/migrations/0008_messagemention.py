import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0007_messagereaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageMention",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mentions",
                        to="chat.messages",
                    ),
                ),
                (
                    "mentioned_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mentions_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Message Mention",
                "verbose_name_plural": "Message Mentions",
                "db_table": "message_mentions",
                "unique_together": {("message", "mentioned_user")},
            },
        ),
        migrations.AddIndex(
            model_name="messagemention",
            index=models.Index(fields=["mentioned_user", "read_at"], name="message_men_mention_fdba10_idx"),
        ),
    ]
