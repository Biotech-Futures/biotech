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
