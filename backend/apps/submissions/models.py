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

    # Stable identifier that stored answers are keyed by. Kept separate from
    # ``prompt`` so the wording can be rewritten freely — fixing a typo must
    # never orphan answers students have already written.
    key = models.CharField(max_length=32, unique=True)
    prompt = models.TextField()
    help_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    # Blank means no limit. Words rather than characters because that is the
    # rule the competition actually publishes ("max 150 words each") and the
    # one their Qualtrics form enforces.
    max_words = models.PositiveIntegerField(null=True, blank=True)
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

    @staticmethod
    def count_words(text: str) -> int:
        """Words in an answer, counted the way the competition's form does.

        Qualtrics validates these answers with ``^\\s*(\\S+\\s+){0,149}\\S*$``,
        which is simply "runs of non-whitespace separated by whitespace". Any
        cleverer definition — stripping punctuation, handling hyphenation —
        would disagree with the tool students were previously measured by.
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
    # Displayed as the section's title, with `body` as the line beneath it —
    # the same shape the client's Qualtrics form uses ("Short Answer Questions"
    # above "Max 150 words each").
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
    # Extra time accepted after closes_at without announcing it. The programme
    # publishes one date but stays deliberately generous, so that a student in
    # a timezone well behind the announced one is not cut off partway through
    # their own deadline day. Students are shown closes_at; the server enforces
    # closes_at + grace_hours.
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


class Submission(models.Model):
    """One team's entry. Resubmitting updates this row rather than adding one.

    Keeping a single row per team means the history of earlier attempts is not
    retained. That is a deliberate simplification: a full version history is
    what a judging system needs in order to prove what existed at the moment
    the deadline passed, and judging is out of scope here.
    """

    # OneToOne rather than ForeignKey so the database itself refuses a second
    # submission for the same team, instead of relying on application code.
    #
    # A consequence worth being explicit about: a team can hold exactly one
    # entry, ever. That is safe because group names come from a single
    # continuous series (``Groups.create_auto_named``) rather than restarting
    # each year, so a team re-forming for a later competition is a new group.
    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission",
    )

    # Which competition year this entry belongs to. Stored rather than inferred
    # from ``submitted_at`` because the two genuinely disagree: a deadline in
    # September with a grace window, or a granted extension, can put the act of
    # submitting in a different calendar year from the competition itself.
    # Indexed because "every entry in this cohort" is the query a judging or
    # reporting tool runs first. The authoritative value is written at submit
    # (see services.current_cohort); the default only covers drafts.
    cohort = models.PositiveIntegerField(default=_default_cohort, db_index=True)

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

    # What the format checks found when the poster was uploaded: whether it
    # carried readable text, and any requirement it did not visibly meet.
    #
    # Recorded rather than recomputed on read for two reasons. The checks parse
    # the file, so answering "was this poster in order?" for a list of teams
    # would mean fetching every poster out of blob storage. And the answer is
    # about the file as it was accepted — rewording a check later must not
    # retroactively change what a team was told at the time.
    #
    # Only the warnings are kept: a poster failing a structural check is never
    # stored in the first place, so there is nothing to record about it.
    poster_checks = models.JSONField(null=True, blank=True)

    # --- the submitted copy -------------------------------------------------
    # Taken at the moment of submitting and left alone afterwards. Editing works
    # on the live fields above, so a team that reopens their entry and does not
    # finish still has exactly what they submitted. Without this, abandoning a
    # resubmission would quietly replace a valid entry with a half-edited one.
    submitted_answers = models.JSONField(null=True, blank=True)
    submitted_poster = models.JSONField(null=True, blank=True)
    # Frozen with the rest of the entry, so a marker sees what was flagged
    # about the poster that was actually submitted rather than about one
    # uploaded afterwards during an abandoned revision.
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
    # Set when a team chooses to resubmit. Later than submitted_at means they
    # are editing again; the submitted copy above stays put until they finish.
    reopened_at = models.DateTimeField(null=True, blank=True)
    # Recorded at the moment of submitting rather than computed on read, so a
    # later change to the deadline cannot retroactively make an entry late.
    is_late = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submission"
        verbose_name = "Submission"

    # Slots whose file details are copied into the submitted set.
    FILE_SLOTS = ("poster", "report", "prototype")

    def __str__(self):
        return f"{self.group} ({self.status})"

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
    def status(self) -> str:
        return "submitted" if self.is_locked else "in_progress"

    def snapshot(self, user):
        """Copy the working entry into the submitted set.

        Called only once a submission passes validation, which is what makes an
        abandoned resubmission harmless — nothing here runs until a team
        actually finishes.
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

        A replaced file cannot be deleted while the submitted copy points at
        it, or reopening an entry and swapping a file would destroy what was
        actually submitted.
        """
        keys = set()
        for slot in self.FILE_SLOTS:
            stored = getattr(self, f"submitted_{slot}") or {}
            key = stored.get("storage_key")
            if key:
                keys.add(key)
        return keys
