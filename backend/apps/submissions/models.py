"""Models for team competition submissions: questions, deadlines and entries."""
from django.conf import settings
from django.db import models
from django.utils import timezone


# Read by the page and by cohort reports, so these strings are a contract.
STAGE_NOT_STARTED = "not_started"
STAGE_IN_PROGRESS = "in_progress"
STAGE_SUBMITTED = "submitted"
STAGE_REVISING = "revising"


def _default_cohort() -> int:
    """Fallback cohort for a draft; replaced with the real cohort on submit."""
    return timezone.now().year


class SubmissionQuestion(models.Model):
    """One short-answer question on the entry form."""

    # Separate from prompt so rewording a question never orphans its answers.
    key = models.CharField(max_length=32, unique=True)
    prompt = models.TextField()
    help_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    # Blank means no limit.
    max_words = models.PositiveIntegerField(null=True, blank=True)
    # Retired rather than deleted, so existing answers keep their label.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "submission_question"
        verbose_name = "Submission question"
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self):
        return f"{self.key}: {self.prompt[:60]}"

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True)

    @staticmethod
    def count_words(text: str) -> int:
        return len((text or "").split())


class SubmissionInstruction(models.Model):
    """Guidance shown above each section of the entry form, editable by admins."""

    class Section(models.TextChoices):
        QUESTIONS = "questions", "Questions"
        POSTER = "poster", "Poster"
        EXTRAS = "extras", "Additional materials"

    section = models.CharField(max_length=32, choices=Section.choices, unique=True)
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
    """The closing time that applies to every team without an extension."""

    closes_at = models.DateTimeField()
    # Unannounced extra time: students see closes_at, the server enforces the sum.
    grace_hours = models.PositiveIntegerField(default=0)
    # Only the active row is consulted; past rows are kept on record.
    is_active = models.BooleanField(default=True)
    # Who announced it — shown on the admin page so a changed deadline has a
    # name attached. Null for rows created before this field (or via scripts).
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deadlines_set",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "submission_deadline"
        verbose_name = "Deadline"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Deadline closing {self.closes_at:%Y-%m-%d %H:%M} UTC"


class GroupExtension(models.Model):
    """Extra time granted to one team.

    Revoked rows are kept as history; only one ACTIVE (un-revoked) extension
    may exist per group — enforced by a partial unique constraint.
    """

    group = models.ForeignKey(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission_extensions",
    )
    extended_until = models.DateTimeField()
    # Same quiet buffer as the global deadline: students see extended_until,
    # the server keeps accepting for these hours after it.
    grace_hours = models.PositiveIntegerField(default=0)
    reason = models.TextField(blank=True)
    granted_at = models.DateTimeField(default=timezone.now)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_submission_extensions",
    )
    # Soft revoke: the row is kept as the audit trail (who revoked, when);
    # readers that decide whether a team can still submit ignore revoked rows.
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_submission_extensions",
    )

    class Meta:
        db_table = "submission_group_extension"
        verbose_name = "Group extension"
        constraints = [
            models.UniqueConstraint(
                fields=["group"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_extension_per_group",
            )
        ]

    def __str__(self):
        return f"{self.group} until {self.extended_until:%Y-%m-%d %H:%M} UTC"


class SubmissionReminder(models.Model):
    """The last day a team was reminded, so a rerun job never emails twice."""

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
    """One team's entry. Resubmitting updates this row rather than adding one."""

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="submission",
    )

    # Stored, since a grace window can put submitting in a different year.
    cohort = models.PositiveIntegerField(default=_default_cohort, db_index=True)

    # Keyed by question key.
    answers = models.JSONField(default=dict, blank=True)

    # Each attachment is {"storage_key", "name", "mime", "size"}.
    poster = models.JSONField(null=True, blank=True)
    report = models.JSONField(null=True, blank=True)
    prototype = models.JSONField(null=True, blank=True)
    prototype_url = models.URLField(blank=True)

    # What the format checks found at upload.
    poster_checks = models.JSONField(null=True, blank=True)

    # The submitted copy, frozen at submit so an abandoned revision leaves it intact.
    submitted_answers = models.JSONField(null=True, blank=True)
    submitted_poster = models.JSONField(null=True, blank=True)
    submitted_poster_checks = models.JSONField(null=True, blank=True)
    submitted_report = models.JSONField(null=True, blank=True)
    submitted_prototype = models.JSONField(null=True, blank=True)
    submitted_prototype_url = models.URLField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions_made",
    )
    # Later than submitted_at means the team is editing again.
    reopened_at = models.DateTimeField(null=True, blank=True)
    # Recorded at submit, so a later deadline change cannot make an entry late.
    is_late = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submission"
        verbose_name = "Submission"

    FILE_SLOTS = ("poster", "report", "prototype")

    def __str__(self):
        return f"{self.group} ({self.stage})"

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None

    @property
    def is_locked(self) -> bool:
        """Submitted and not currently reopened."""
        if self.submitted_at is None:
            return False
        return self.reopened_at is None or self.reopened_at <= self.submitted_at

    @property
    def has_content(self) -> bool:
        if any(str(value).strip() for value in (self.answers or {}).values()):
            return True
        if self.prototype_url:
            return True
        return any(getattr(self, slot) for slot in self.FILE_SLOTS)

    @property
    def stage(self) -> str:
        """How far the entry has got, independent of whether the deadline has passed."""
        if self.submitted_at is None:
            return STAGE_IN_PROGRESS if self.has_content else STAGE_NOT_STARTED
        return STAGE_SUBMITTED if self.is_locked else STAGE_REVISING

    def snapshot(self, user):
        """Copy the working entry into the submitted set."""
        self.submitted_answers = dict(self.answers or {})
        for slot in self.FILE_SLOTS:
            setattr(self, f"submitted_{slot}", getattr(self, slot))
        self.submitted_prototype_url = self.prototype_url
        self.submitted_poster_checks = self.poster_checks
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.reopened_at = None

    def submitted_storage_keys(self) -> set[str]:
        """Storage keys the submitted copy still points at, which must not be deleted."""
        keys = set()
        for slot in self.FILE_SLOTS:
            stored = getattr(self, f"submitted_{slot}") or {}
            key = stored.get("storage_key")
            if key:
                keys.add(key)
        return keys
