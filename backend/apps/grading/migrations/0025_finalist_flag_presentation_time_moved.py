"""The finalist flag's presentation time moved to Management's
PresentationAllocation (its 0002, which copied them across first)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0024_management_models_moved'),
        ('management', '0002_presentation_allocation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='finalistflag',
            name='presentation_slot',
        ),
    ]
