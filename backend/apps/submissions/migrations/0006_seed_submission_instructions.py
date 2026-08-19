"""Seed the guidance text that was previously hardcoded in the entry page.

Carrying the existing wording across means nothing changes visibly; the only
difference is that the programme team can now reword it themselves. It stays
placeholder wording until the client supplies their own.
"""
from django.db import migrations


SEED_INSTRUCTIONS = {
    "questions": (
        "Answer each question in your own words. Nothing is sent anywhere until you press "
        "Submit, and you can keep editing right up to the deadline."
    ),
    "poster": (
        "Upload your poster as a single PDF. It appears below once uploaded, so you can check "
        "the right file arrived and that it exported correctly. A poster is required before "
        "you can submit."
    ),
    "extras": (
        "Attach a scientific report as a PDF if you have written one, and a prototype as a "
        "file or a link."
    ),
}


def seed_instructions(apps, schema_editor):
    SubmissionInstruction = apps.get_model("submissions", "SubmissionInstruction")
    for section, body in SEED_INSTRUCTIONS.items():
        # get_or_create rather than update: never clobber wording an admin has
        # already changed.
        SubmissionInstruction.objects.get_or_create(
            section=section, defaults={"body": body}
        )


def remove_instructions(apps, schema_editor):
    SubmissionInstruction = apps.get_model("submissions", "SubmissionInstruction")
    SubmissionInstruction.objects.filter(section__in=SEED_INSTRUCTIONS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0005_submissioninstruction"),
    ]

    operations = [
        migrations.RunPython(seed_instructions, remove_instructions),
    ]
