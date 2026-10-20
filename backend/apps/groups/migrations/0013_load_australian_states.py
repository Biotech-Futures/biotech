"""Load Australia's 8 states and territories, so every database has them
without waiting for a student from each to register. Written as registration
and the CSV imports send them (NSW, VIC, ...), and only added when missing,
by code or full name, so nothing is duplicated."""
from django.db import migrations

# Each code, with the full name a database may have it under instead.
AUSTRALIAN_STATES = {
    "NSW": "New South Wales",
    "VIC": "Victoria",
    "QLD": "Queensland",
    "WA": "Western Australia",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "ACT": "Australian Capital Territory",
    "NT": "Northern Territory",
}


def add_missing_states(apps, schema_editor):
    Countries = apps.get_model("groups", "Countries")
    CountryStates = apps.get_model("groups", "CountryStates")
    australia = Countries.objects.filter(country_name__iexact="Australia").first()
    if australia is None:
        return
    have = {name.lower() for name in CountryStates.objects.filter(country=australia).values_list("state_name", flat=True)}
    CountryStates.objects.bulk_create(
        [
            CountryStates(country=australia, state_name=code)
            for code, full_name in AUSTRALIAN_STATES.items()
            if code.lower() not in have and full_name.lower() not in have
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0012_load_countries"),
    ]

    operations = [
        # Nothing to undo: the states stay, as people may be using them.
        migrations.RunPython(add_missing_states, migrations.RunPython.noop),
    ]
