"""Known reference data for the submission tests.

The competition questions and the per-section guidance both reach a real
database through data migrations (``0010_real_question_set``,
``0006_seed_submission_instructions``). Tests must not rely on that: CI runs with
``MIGRATION_MODULES`` disabled (see ``config/settings_test``) so the schema is
built straight from the models and **no data migration ever executes**. Tests
written against the seeded rows therefore pass locally and fail in CI — which
is exactly what happened.

Installing the set explicitly makes every test independent of migration state,
so the suite behaves identically under ``settings_local`` and ``settings_test``.
It also means rewording the real questions cannot break unrelated tests.
"""
from apps.submissions.models import SubmissionInstruction, SubmissionQuestion


# Same shape as the real set, but deliberately generic wording: these exercise
# the mechanism rather than assert the competition's copy.
QUESTIONS = (
    ("solution_purpose", "What does your solution do?"),
    ("inspiration", "What was the inspiration for your solution?"),
    ("research", "What research did you carry out?"),
    ("development", "How did you develop your solution?"),
    ("challenges", "What challenges did you face?"),
    ("future_work", "What would you do next?"),
)

MAX_WORDS = 150


def install_question_set():
    """Replace any existing questions with a known, deterministic set.

    Deletes first so the result does not depend on whether migrations happened
    to have seeded anything — the same reason this helper exists at all.
    """
    SubmissionQuestion.objects.all().delete()
    return [
        SubmissionQuestion.objects.create(
            key=key,
            prompt=prompt,
            order=index,
            is_required=True,
            max_words=MAX_WORDS,
            is_active=True,
        )
        for index, (key, prompt) in enumerate(QUESTIONS)
    ]


# Guidance shown above each section of the form. Seeded by a data migration in a
# real database, so tests install it here for the same reason as the questions.
INSTRUCTIONS = (
    ("questions", "Short Answer Questions", "Max 150 words each."),
    ("poster", "Poster", "Upload your poster as a PDF."),
    ("extras", "Additional Materials", "Optional supporting material."),
)


def install_instructions():
    """Replace any existing guidance with a known block per section."""
    SubmissionInstruction.objects.all().delete()
    return [
        SubmissionInstruction.objects.create(section=section, heading=heading, body=body)
        for section, heading, body in INSTRUCTIONS
    ]


def install_reference_data():
    """Everything the endpoints expect to already exist."""
    return install_question_set(), install_instructions()
