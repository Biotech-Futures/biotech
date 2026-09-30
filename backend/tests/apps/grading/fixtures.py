"""Shared fixtures for the grading test suite.

Split out of the original monolithic test module: every test file in this
package builds on ``_GradingFixture`` (one group with a submitted entry, the
seeded components, SAQ + POSTER rubrics, a staff user) and the docx template
helpers below.
"""
import io
from datetime import datetime, timedelta
from decimal import Decimal
from importlib import import_module

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.grading.models import (
    GradingSettings,
    Rubric,
    RubricCriterion,
    SubmissionComponent,
)
from apps.groups.models.groups import Groups
from apps.submissions.models import Submission, SubmissionQuestion
from apps.submissions.services import current_cohort
from apps.users.models import User


def _build_docx(text: str) -> bytes:
    """A one-paragraph docx for template fixtures."""
    from docx import Document as NewDocument

    doc = NewDocument()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _seed_doc_templates():
    """Upload token templates — no fallbacks ship in the repo any more."""
    row = GradingSettings.load()
    row.marks_summary_template = SimpleUploadedFile(
        "marks.docx",
        _build_docx(
            "Team {{TeamCode}} S1 {{SM1}} ({{ShortAnswerQuestionComment1}}) total {{CombinedTotal}} "
            "poster: {{PosterOverallComment}}"
        ),
    )
    row.certificate_template = SimpleUploadedFile(
        "cert.docx", _build_docx("{{Name}} — {{ProjectTitle}}")
    )
    row.mentor_certificate_template = SimpleUploadedFile(
        "mentor.docx", _build_docx("{{Name}} mentored {{ProjectTitle}}")
    )
    row.save()
    return row



def just_closed(hours: float = 24) -> datetime:
    """A closing time ``hours`` ago, but never before this year began. The
    competition year comes from the deadline, so on New Year's Day "a day ago"
    would make last year the cohort, not this year's teams made in the test."""
    now = timezone.now()
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(now - timedelta(hours=hours), start_of_year)

class _GradingFixture(TestCase):
    """Shared setup: one group with a submitted entry (SAQ answers + a poster),
    four seeded components, SAQ + POSTER rubrics, one staff user.

    A team's entry is one Submission row; ``saq_submission`` and
    ``poster_submission`` are kept as aliases of it so the per-component tests
    read naturally — grades tell components apart via their criterion.
    """

    @classmethod
    def setUpTestData(cls):
        # settings_test disables migrations entirely, so the 0002_seed_components
        # data migration never runs there — seed the same rows ourselves, reusing
        # the migration's own COMPONENTS list so the two can't drift.
        seed_components = import_module(
            "apps.grading.migrations.0002_seed_components"
        ).COMPONENTS
        for row in seed_components:
            SubmissionComponent.objects.update_or_create(
                code=row["code"],
                defaults={k: v for k, v in row.items() if k != "code"},
            )

        cls.group = Groups.objects.create(group_name="BTF-TEST-1")
        cls.saq = SubmissionComponent.objects.get(code="SAQ")
        cls.poster = SubmissionComponent.objects.get(code="POSTER")

        # This year's rubrics, as the app looks them up: never a fixed year,
        # which would stop matching once the calendar moves on.
        cls.year = current_cohort()
        cls.saq_rubric = Rubric.objects.create(component=cls.saq, year=cls.year, active=True)
        cls.poster_rubric = Rubric.objects.create(component=cls.poster, year=cls.year, active=True)

        cls.saq_c1 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Content", max_mark=Decimal("10.00"), order=10)
        cls.saq_c2 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Clarity", max_mark=Decimal("5.00"), order=20)
        cls.poster_c1 = RubricCriterion.objects.create(rubric=cls.poster_rubric, name="Design", max_mark=Decimal("10.00"), order=10)

        cls.staff = User.objects.create_user(
            email="grader@example.com", first_name="Ada", last_name="Grader",
            password="pw12345!", is_staff=True,
        )
        cls.non_staff = User.objects.create_user(
            email="student@example.com", first_name="Stu", last_name="Dent",
            password="pw12345!", is_staff=False,
        )

        # A question so the SAQ export carries a heading, not a raw key.
        SubmissionQuestion.objects.create(
            key="q_answers", prompt="Team answers", order=10,
        )
        cls.submission = Submission.objects.create(
            group=cls.group,
            answers={"q_answers": "Some student answers."},
            poster={"storage_key": "2026/01/01/fixture/poster.pdf",
                    "name": "poster.pdf", "mime": "application/pdf", "size": 42},
        )
        cls.submission.snapshot(cls.staff)
        cls.submission.save()
        # One row, two component views of it.
        cls.saq_submission = cls.submission
        cls.poster_submission = cls.submission
