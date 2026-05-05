import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_alter_messages_message_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="messages",
            name="reply_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replies",
                to="chat.messages",
            ),
        ),
        migrations.AddIndex(
            model_name="messages",
            index=models.Index(fields=["reply_to"], name="messages_reply_t_313c91_idx"),
        ),
    ]
