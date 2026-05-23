from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0003_alter_groupmembership_membership_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='tracks',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
    ]
