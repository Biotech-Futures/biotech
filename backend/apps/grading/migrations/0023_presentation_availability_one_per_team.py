import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0022_group_presentation_availability'),
        ('groups', '__first__'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='presentationavailability',
            name='uniq_presentation_availability',
        ),
        migrations.RemoveField(
            model_name='presentationavailability',
            name='user',
        ),
        migrations.AlterField(
            model_name='presentationavailability',
            name='group',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='presentation_availability', to='groups.groups'),
        ),
    ]
