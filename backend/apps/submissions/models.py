"""Models for the team submission platform.

A team fills in a set of short-answer questions and attaches up to three files
(a poster, an optional scientific report, and an optional prototype) plus an
optional link. They may keep changing their entry until the deadline passes.

Scope notes, deliberate for this first version:

* Entries are **per team**. There is no route for a student who is not in a
  group to submit on their own; whether the competition allows that is an open
  question with the client.
* There is a **single submission round**. No column records which year or round
  a submission belongs to, so a second round would need a schema change.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class SubmissionQuestion(models.Model):
    """One short-answer question on the entry form.

    Questions live here rather than in the frontend so they can be reworded,
    reordered or retired without a code change, and — just as importantly — so
    the server knows what each stored answer *means*. Exporting answers to a
    spreadsheet needs column headings, and a bare ``{"q1": ...}`` blob cannot
    supply them.
    """

    # Stable identifier that stored answers are keyed by. Kept separate from
    # ``prompt`` so the wording can be rewritten freely — fixing a typo must
    # never orphan answers students have already written.
    key = models.CharField(max_length=32, unique=True)
    prompt = models.TextField()
    help_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    # Blank means no limit.
    max_length = models.PositiveIntegerField(null=True, blank=True)
    # Retired rather than deleted: deleting would strand the matching answers
    # in the JSON with nothing left to label them.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "submission_question"
        verbose_name = "Submission question"
        # ``order`` is not unique — swapping two questions around would
        # otherwise need a temporary value to dodge the constraint. ``id``
        # breaks ties so the sequence is still stable.
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self):
        return f"{self.key}: {self.prompt[:60]}"

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True)


class SubmissionInstruction(models.Model):
    """Guidance shown above each section of the entry form.

    Held here rather than in the page so the programme team can reword their
    own guidance without a code change. The wording is expected to be revised
    several times before a competition runs, and each revision would otherwise
    need a developer and a deploy.
    """

    class Section(models.TextChoices):
        QUESTIONS = "questions", "Questions"
        POSTER = "poster", "Poster"
        EXTRAS = "extras", "Additional materials"

    # One block per section of the form; the section names match the tabs.
    section = models.CharField(max_length=32, choices=Section.choices, unique=True)
    body = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submission_instruction"
        verbose_name = "Submission instruction"
        ordering = ["section"]

    def __str__(self):
        return self.get_section_display()


class Deadline(models.Model):
    """The closing time that applies to every team by default.

    Individual teams can be given more time through :class:`GroupExtension`;
    this row is the baseline everything else is measured against.
    """

    closes_at = models.DateTimeField()
    # Rows are kept rather than deleted so a past round stays on record. Only
    # the active one is consulted when deciding whether submissions are open.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "submission_deadline"
        verbose_name = "Deadline"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Deadline closing {self.closes_at:%Y-%m-%d %H:%M} UTC"


class GroupExtension(models.Model):
    """Extra time granted to one team.

    Only teams that were actually given an extension have a row here, so the
    absence of a row is the normal case and means "use the standard deadline".
    """

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission_extension",
    )
    extended_until = models.DateTimeField()
    reason = models.TextField(blank=True)
    granted_at = models.DateTimeField(default=timezone.now)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_submission_extensions",
    )

    class Meta:
        db_table = "submission_group_extension"
        verbose_name = "Group extension"

    def __str__(self):
        return f"{self.group} until {self.extended_until:%Y-%m-%d %H:%M} UTC"


class Submission(models.Model):
    """One team's entry. Resubmitting updates this row rather than adding one.

    Keeping a single row per team means the history of earlier attempts is not
    retained. That is a deliberate simplification: a full version history is
    what a judging system needs in order to prove what existed at the moment
    the deadline passed, and judging is out of scope here.
    """

    # OneToOne rather than ForeignKey so the database itself refuses a second
    # submission for the same team, instead of relying on application code.
    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission",
    )

    # Short-answer responses, keyed by question id: {"q1": "...", "q2": "..."}.
    # Held as JSON because the real questions are not known yet — they come
    # from the client's existing Qualtrics form. This lets the question set
    # change without a database migration each time.
    answers = models.JSONField(default=dict, blank=True)

    # Each attachment is stored as one JSON object holding everything needed to
    # serve the file back: {"storage_key", "name", "mime", "size"}. Three flat
    # columns rather than twelve, and nothing ever needs to search inside them
    # — they are only ever read back for a single team at a time.
    poster = models.JSONField(null=True, blank=True)
    report = models.JSONField(null=True, blank=True)
    prototype = models.JSONField(null=True, blank=True)
    prototype_url = models.URLField(blank=True)

    # Empty submitted_at means the team has saved a draft but not submitted.
    # Avoids a separate status field that could drift out of step with this one.
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions_made",
    )
    # Recorded at the moment of submitting rather than computed on read, so a
    # later change to the deadline cannot retroactively make an entry late.
    is_late = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submission"
        verbose_name = "Submission"

    def __str__(self):
        state = "submitted" if self.submitted_at else "draft"
        return f"{self.group} ({state})"

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None
