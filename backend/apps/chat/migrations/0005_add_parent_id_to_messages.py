from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_alter_messages_message_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='messages',
            name='parent_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
