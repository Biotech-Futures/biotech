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


# How far an entry has got. Read by the page and by anything reporting on a
# cohort, so these strings are a contract rather than display text.
STAGE_NOT_STARTED = "not_started"
STAGE_IN_PROGRESS = "in_progress"
STAGE_SUBMITTED = "submitted"
STAGE_REVISING = "revising"


def _default_cohort() -> int:
    """Fallback cohort for a draft row.

    Deliberately a plain year rather than a lookup: this module cannot import
    ``services`` (which imports these models), and a draft's cohort is
    overwritten with the authoritative value when the entry is submitted.
    """
    return timezone.now().year


class SubmissionQuestion(models.Model):
    """One short-answer question on the entry form.

    Questions live here rather than in the frontend so they can be reworded,
    reordered or retired without a code change, and — just as importantly — so
    the server knows what each stored answer *means*. Exporting answers to a
    spreadsheet needs column headings, and a bare ``{"q1": ...}`` blob cannot
    supply them.
    """

    # Kept separate from ``prompt`` so wording can change freely: fixing a
    # typo must never orphan answers students have already written.
    key = models.CharField(max_length=32, unique=True)
    prompt = models.TextField()
    help_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    # Blank means no limit. Words rather than characters, matching the rule
    # the competition publishes and its Qualtrics form enforces.
    max_words = models.PositiveIntegerField(null=True, blank=True)
    # Retired rather than deleted: deleting would strand the matching answers
    # in the JSON with nothing left to label them.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "submission_question"
        verbose_name = "Submission question"
        # Not unique: swapping two questions would otherwise need a temporary
        # value to dodge the constraint. ``id`` breaks ties.
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self):
        return f"{self.key}: {self.prompt[:60]}"

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True)

    @staticmethod
    def count_words(text: str) -> int:
        """Words in an answer, counted the way the competition's form does.

        Whitespace-separated runs. Anything cleverer would disagree with the
        tool students were previously measured by.
        """
        return len((text or "").split())


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
    # The section's title, with `body` beneath it — the shape the client's
    # Qualtrics form uses.
    heading = models.CharField(max_length=120, blank=True)
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
    # Unannounced extra time, so a student in a far-behind timezone is not cut
    # off mid-deadline-day. Students see closes_at; the server enforces the sum.
    grace_hours = models.PositiveIntegerField(default=0)
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


class SubmissionReminder(models.Model):
    """The last day a team was reminded about their unfinished entry.

    Keyed by team, not submission: the teams most needing a reminder have no
    submission row at all. Only the date is kept, so a job that runs twice in
    one day cannot email anyone twice.
    """

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission_reminder",
    )
    last_sent_on = models.DateField()

    class Meta:
        db_table = "submission_reminder"
        verbose_name = "Submission reminder"

    def __str__(self):
        return f"{self.group} last reminded {self.last_sent_on}"


class Submission(models.Model):
    """One team's entry. Resubmitting updates this row rather than adding one.

    Keeping a single row per team means the history of earlier attempts is not
    retained. That is a deliberate simplification: a full version history is
    what a judging system needs in order to prove what existed at the moment
    the deadline passed, and judging is out of scope here.
    """

    # OneToOne so the database itself refuses a second entry per team. A team
    # holds one entry ever; group names never restart, so next year is a new group.
    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission",
    )

    # Stored, not inferred from submitted_at: a grace window or extension can
    # put the act of submitting in a different year from the competition.
    cohort = models.PositiveIntegerField(default=_default_cohort, db_index=True)

    # Keyed by question key. JSON so the question set can change without a
    # migration each time.
    answers = models.JSONField(default=dict, blank=True)

    # One JSON object per attachment: {"storage_key", "name", "mime", "size"}.
    # Three columns rather than twelve; nothing ever searches inside them.
    poster = models.JSONField(null=True, blank=True)
    report = models.JSONField(null=True, blank=True)
    prototype = models.JSONField(null=True, blank=True)
    prototype_url = models.URLField(blank=True)

    # What the checks found at upload. Recorded, not recomputed: reading it back
    # would mean fetching every poster out of blob storage.
    poster_checks = models.JSONField(null=True, blank=True)

    # --- the submitted copy: frozen at submit, so an abandoned revision
    # leaves what was submitted intact -----------------------------------------
    submitted_answers = models.JSONField(null=True, blank=True)
    submitted_poster = models.JSONField(null=True, blank=True)
    # Frozen with the poster it describes, so a marker never reads a flag about
    # a different file.
    submitted_poster_checks = models.JSONField(null=True, blank=True)
    submitted_report = models.JSONField(null=True, blank=True)
    submitted_prototype = models.JSONField(null=True, blank=True)
    submitted_prototype_url = models.URLField(blank=True)

    # Empty submitted_at means the team has saved a draft but never submitted.
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions_made",
    )
    # Later than submitted_at means they are editing again; the submitted copy
    # stays put until they finish.
    reopened_at = models.DateTimeField(null=True, blank=True)
    # Recorded at submit, so a later deadline change cannot retroactively make
    # an entry late.
    is_late = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submission"
        verbose_name = "Submission"

    # Slots whose file details are copied into the submitted set.
    FILE_SLOTS = ("poster", "report", "prototype")

    def __str__(self):
        return f"{self.group} ({self.stage})"

    @property
    def is_submitted(self) -> bool:
        """A completed submission exists, whether or not it is being revised."""
        return self.submitted_at is not None

    @property
    def is_locked(self) -> bool:
        """Editing is closed: submitted, and not currently reopened."""
        if self.submitted_at is None:
            return False
        return self.reopened_at is None or self.reopened_at <= self.submitted_at

    @property
    def has_content(self) -> bool:
        """Anything at all filled in, so an untouched entry can be told apart."""
        if any(str(value).strip() for value in (self.answers or {}).values()):
            return True
        if self.prototype_url:
            return True
        return any(getattr(self, slot) for slot in self.FILE_SLOTS)

    @property
    def stage(self) -> str:
        """How far the entry has got, said independently of the deadline.

        Deliberately knows nothing about whether submissions are still open:
        that is a fact about the competition, not about this entry, and keeping
        the two apart is what lets a caller answer "submitted but closed"
        without a third state existing for it.
        """
        if self.submitted_at is None:
            return STAGE_IN_PROGRESS if self.has_content else STAGE_NOT_STARTED
        return STAGE_SUBMITTED if self.is_locked else STAGE_REVISING

    def snapshot(self, user):
        """Copy the working entry into the submitted set.

        Runs only once a submission passes validation, which is what makes an
        abandoned revision harmless.
        """
        self.submitted_answers = dict(self.answers or {})
        for slot in self.FILE_SLOTS:
            setattr(self, f"submitted_{slot}", getattr(self, slot))
        self.submitted_prototype_url = self.prototype_url
        # Travels with the poster it describes; copying one without the other
        # would leave a marker reading a flag about a different file.
        self.submitted_poster_checks = self.poster_checks
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.reopened_at = None

    def submitted_storage_keys(self) -> set[str]:
        """Storage keys the submitted copy still depends on.

        A file the submitted copy points at must survive being replaced.
        """
        keys = set()
        for slot in self.FILE_SLOTS:
            stored = getattr(self, f"submitted_{slot}") or {}
            key = stored.get("storage_key")
            if key:
                keys.add(key)
        return keys
