"""Seed the placeholder question set.

An empty question table would render an entry form with no questions at all, so
the four that were previously hardcoded in the frontend are inserted here. The
keys match the ones already stored in existing ``Submission.answers`` blobs, so
answers written before this migration keep displaying against the right
question.

The wording is a placeholder until the client supplies their current Qualtrics
form. Reordering, rewording, changing which are required, or retiring any of
them is an admin edit from here on, not a code change.
"""
from django.db import migrations


# (key, prompt, order)
SEED_QUESTIONS = [
    ("q1", "What problem does your project address?", 1),
    ("q2", "Describe your approach and methodology.", 2),
    ("q3", "What are your key findings or results?", 3),
    ("q4", "What impact could your project have?", 4),
]


def seed_questions(apps, schema_editor):
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")
    for key, prompt, order in SEED_QUESTIONS:
        # get_or_create keeps this safe to re-run and avoids clobbering any
        # wording an admin has already adjusted.
        SubmissionQuestion.objects.get_or_create(
            key=key,
            defaults={
                "prompt": prompt,
                "order": order,
                "is_required": True,
                "is_active": True,
            },
        )


def remove_questions(apps, schema_editor):
    # Only the seeded keys are removed; anything an admin added by hand stays.
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")
    SubmissionQuestion.objects.filter(
        key__in=[key for key, _, _ in SEED_QUESTIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0002_submissionquestion"),
    ]

    operations = [
        migrations.RunPython(seed_questions, remove_questions),
    ]
