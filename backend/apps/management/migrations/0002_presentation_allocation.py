"""Each finalist team's presentation time moves off its finalist flag
(grading) into a table of its own here. The times are copied across; grading's
0025 then drops the old column."""
import django.db.models.deletion
from django.db import migrations, models


def copy_times(apps, schema_editor):
    FinalistFlag = apps.get_model("grading", "FinalistFlag")
    PresentationAllocation = apps.get_model("management", "PresentationAllocation")
    PresentationAllocation.objects.bulk_create(
        PresentationAllocation(flag_id=flag_id, slot_id=slot_id)
        for flag_id, slot_id in FinalistFlag.objects.filter(presentation_slot__isnull=False).values_list(
            "id", "presentation_slot_id"
        )
    )


def copy_times_back(apps, schema_editor):
    FinalistFlag = apps.get_model("grading", "FinalistFlag")
    PresentationAllocation = apps.get_model("management", "PresentationAllocation")
    for flag_id, slot_id in PresentationAllocation.objects.values_list("flag_id", "slot_id"):
        FinalistFlag.objects.filter(id=flag_id).update(presentation_slot_id=slot_id)


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0024_management_models_moved'),
        ('management', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PresentationAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flag', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='presentation_allocation', to='grading.finalistflag')),
                ('slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='management.presentationslot')),
            ],
            options={
                'db_table': 'presentation_allocation',
            },
        ),
        migrations.RunPython(copy_times, copy_times_back),
    ]
