from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('emoji_string', models.CharField(max_length=64)),
                ('message', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='chat.messages',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='message_reactions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'message_reactions',
                'verbose_name': 'Message Reaction',
                'verbose_name_plural': 'Message Reactions',
            },
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['message'], name='msg_reaction_message_idx'),
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['user'], name='msg_reaction_user_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='messagereaction',
            unique_together={('message', 'user', 'emoji_string')},
        ),
    ]