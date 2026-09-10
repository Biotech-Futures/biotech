"""Give the placeholder questions a character limit.

A limit is what makes the page show a live character count, which students
expect on this kind of form. 1,500 is a stand-in until the client confirms what
their Qualtrics form actually allows — it is an admin field, so adjusting it
later needs no code change.

Only questions with no limit set are touched, so a limit an admin has already
chosen is never overwritten.
"""
from django.db import migrations


PLACEHOLDER_LIMIT = 1500
SEEDED_KEYS = ["q1", "q2", "q3", "q4"]


def set_limits(apps, schema_editor):
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")
    SubmissionQuestion.objects.filter(
        key__in=SEEDED_KEYS, max_length__isnull=True
    ).update(max_length=PLACEHOLDER_LIMIT)


def clear_limits(apps, schema_editor):
    SubmissionQuestion = apps.get_model("submissions", "SubmissionQuestion")
    SubmissionQuestion.objects.filter(
        key__in=SEEDED_KEYS, max_length=PLACEHOLDER_LIMIT
    ).update(max_length=None)


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0003_seed_submission_questions"),
    ]

    operations = [
        migrations.RunPython(set_limits, clear_limits),
    ]
