"""Give each section a heading and a short line beneath it.

Follows the client's Qualtrics form, which introduces each part with a title
and one supporting line — "Short Answer Questions" above "Max 150 words each" —
rather than a paragraph of guidance. Both parts stay admin-editable.
"""
from django.db import migrations


SECTIONS = {
    "questions": (
        "Short Answer Questions",
        "Max 150 words each.",
    ),
    "poster": (
        "Poster",
        "Please upload a PDF file of your completed poster.",
    ),
    "extras": (
        "Additional Materials",
        "Optional. Upload a scientific report as a PDF, and a prototype as a file or a link.",
    ),
}


def set_headings(apps, schema_editor):
    SubmissionInstruction = apps.get_model("submissions", "SubmissionInstruction")
    for section, (heading, body) in SECTIONS.items():
        SubmissionInstruction.objects.update_or_create(
            section=section, defaults={"heading": heading, "body": body}
        )


def clear_headings(apps, schema_editor):
    SubmissionInstruction = apps.get_model("submissions", "SubmissionInstruction")
    SubmissionInstruction.objects.filter(section__in=SECTIONS).update(heading="")


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0011_submissioninstruction_heading"),
    ]

    operations = [
        migrations.RunPython(set_headings, clear_headings),
    ]
