"""Load the program's official areas of interest, so the interest tick boxes
(student panel, profile, group editor) offer them on every database, not only
once students have picked them. Only adds the missing ones, matching names
whatever their case, so nothing is duplicated."""
from django.db import migrations

# The official list, as frontend/src/utils/supervisedGroups.ts has it
# (DEFAULT_GROUP_INTERESTS).
AREAS_OF_INTEREST = [
    "Biomedical Innovations",
    "Environmental Sustainability & Climate Tech",
    "Space & Astrobiology",
    "AI & Robotics and Smart Systems",
    "Nanotechnology & Materials Science",
    "Food & Agriculture Technology",
    "Neuroscience & Mental Health Tech",
    "Water & Energy Tech",
    "Ethical & Societal Impacts of Emerging Tech",
]


def add_missing_areas(apps, schema_editor):
    AreasOfInterest = apps.get_model("users", "AreasOfInterest")
    have = {name.lower() for name in AreasOfInterest.objects.values_list("interest_desc", flat=True)}
    AreasOfInterest.objects.bulk_create(
        [AreasOfInterest(interest_desc=name) for name in AREAS_OF_INTEREST if name.lower() not in have]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0022_supervisor_group_order"),
    ]

    operations = [
        # Nothing to undo: the areas stay, as students may have picked them.
        migrations.RunPython(add_missing_areas, migrations.RunPython.noop),
    ]
