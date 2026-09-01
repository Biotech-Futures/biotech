from django.db import migrations


COMPONENTS = [
    {
        "code": "SAQ",
        "name": "Short Answer Questions",
        "is_optional": False,
        "accepts_file": False,
        "accepts_text": True,
        "accepts_link": False,
        "order": 10,
    },
    {
        "code": "POSTER",
        "name": "A2 Poster",
        "is_optional": False,
        "accepts_file": True,
        "accepts_text": False,
        "accepts_link": False,
        "order": 20,
    },
    {
        "code": "REPORT",
        "name": "Scientific Report",
        "is_optional": True,
        "accepts_file": True,
        "accepts_text": False,
        "accepts_link": False,
        "order": 30,
    },
    {
        "code": "PROTOTYPE",
        "name": "Prototype",
        "is_optional": True,
        "accepts_file": True,
        "accepts_text": False,
        "accepts_link": True,
        "order": 40,
    },
]


def seed(apps, schema_editor):
    SubmissionComponent = apps.get_model("submissions", "SubmissionComponent")
    for row in COMPONENTS:
        SubmissionComponent.objects.update_or_create(
            code=row["code"],
            defaults={k: v for k, v in row.items() if k != "code"},
        )


def unseed(apps, schema_editor):
    SubmissionComponent = apps.get_model("submissions", "SubmissionComponent")
    SubmissionComponent.objects.filter(code__in=[c["code"] for c in COMPONENTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
