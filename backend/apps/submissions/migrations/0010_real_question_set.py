"""Replace the placeholder questions with the competition's real set.

Taken from the client's Qualtrics export (BTF_Submission_Portal_2024.qsf). All
six are required and capped at 150 words, matching the validation their form
applies.

Two deliberate differences from the export:

* Their form validates every question's length against the *first* answer, so
  in practice only question one is capped. Ours checks each answer against its
  own limit, which is plainly what was intended.
* Question five reads "How does your solution different to others available?"
  in the export. The wording is corrected here, and is editable in the admin if
  they want it verbatim.

The placeholder questions are retired rather than deleted so that any answers
already written against them keep a label to display.
"""
from django.db import migrations


PLACEHOLDER_KEYS = ["q1", "q2", "q3", "q4"]

# (key, prompt, order)
QUESTIONS = [
    ("solution_purpose", "What does your solution do?", 1),
    ("inspiration", "What was the inspiration for your solution?", 2),
    ("how_it_works", "How does your solution work?", 3),
    ("design_process", "What was the design process used to come to your solution?", 4),
    ("difference", "How is your solution different to others available?", 5),
    ("future_plans", "What future plans do you have for your solution?", 6),
]

MAX_WORDS = 150


def install_real_questions(apps, schema_editor):
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")

    SubmissionQuestion.objects.filter(key__in=PLACEHOLDER_KEYS).update(is_active=False)

    for key, prompt, order in QUESTIONS:
        SubmissionQuestion.objects.update_or_create(
            key=key,
            defaults={
                "prompt": prompt,
                "order": order,
                "is_required": True,
                "max_words": MAX_WORDS,
                "is_active": True,
            },
        )


def restore_placeholders(apps, schema_editor):
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")
    SubmissionQuestion.objects.filter(key__in=[key for key, _, _ in QUESTIONS]).delete()
    SubmissionQuestion.objects.filter(key__in=PLACEHOLDER_KEYS).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0009_question_max_words"),
    ]

    operations = [
        migrations.RunPython(install_real_questions, restore_placeholders),
    ]
