import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_alter_messages_message_type_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessagePreview',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('url', models.TextField()),
                ('title', models.TextField(blank=True, default='')),
                ('description', models.TextField(blank=True, default='')),
                ('image_url', models.TextField(blank=True, default='')),
                ('fetched_at', models.DateTimeField(default=django.utils.timezone.now)),
                (
                    'message',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='preview',
                        to='chat.messages',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Message Preview',
                'verbose_name_plural': 'Message Previews',
                'db_table': 'message_previews',
                'indexes': [
                    models.Index(
                        fields=['message'],
                        name='message_pre_message_idx',
                    ),
                ],
            },
        ),
    ]
