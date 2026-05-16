from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chat", "0011_alter_messages_message_type_messagegif"),
    ]

    operations = [
        migrations.AddField(
            model_name="messages",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deleted_chat_messages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
