"""Measure answer limits in words rather than characters.

The competition publishes "max 150 words each", and the client's Qualtrics form
enforces exactly that with a regex counting whitespace-separated words. Counting
characters was our own invention and would have disagreed with the rule students
are actually given.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0008_submission_reopened_at_submission_submitted_answers_and_more"),
    ]

    operations = [
        # A rename rather than drop-and-add: same column, different unit. The
        # values are replaced by the real question set in the next migration.
        migrations.RenameField(
            model_name="submissionquestion",
            old_name="max_length",
            new_name="max_words",
        ),
    ]
