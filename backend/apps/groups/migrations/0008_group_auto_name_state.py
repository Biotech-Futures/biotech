from django.db import migrations, models
from django.db.models import Max, Value
from django.db.models.functions import Length, LPad, Substr


def seed_auto_name_counter(apps, schema_editor):
    Groups = apps.get_model("groups", "Groups")
    GroupAutoNameState = apps.get_model("groups", "GroupAutoNameState")
    auto_names = Groups.objects.filter(group_name__regex=r"^BTF[0-9]+$").annotate(
        digits=Substr("group_name", 4)
    )
    width = auto_names.aggregate(width=Max(Length("digits")))["width"]
    next_number = 0
    if width:
        highest = auto_names.aggregate(
            highest=Max(LPad("digits", width, Value("0")))
        )["highest"]
        next_number = int(highest) + 1
    GroupAutoNameState.objects.update_or_create(pk=1, defaults={"next_number": next_number})


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0007_group_interest"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupAutoNameState",
            fields=[
                ("id", models.PositiveSmallIntegerField(primary_key=True, serialize=False, default=1)),
                ("next_number", models.PositiveIntegerField(default=0)),
            ],
            options={
                "db_table": "group_auto_name_state",
            },
        ),
        migrations.RunPython(seed_auto_name_counter, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="groups",
            name="unique_active_group_name",
        ),
        migrations.AddIndex(
            model_name="groups",
            index=models.Index(fields=["group_name"], name="groups_group_name_idx"),
        ),
    ]
