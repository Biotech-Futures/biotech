from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0028_merge_20261017_0752'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='admin_notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
