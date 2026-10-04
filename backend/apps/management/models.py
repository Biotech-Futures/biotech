"""Management's models: the release gates, the document setup, the
finalist and results emails, the Symposium's presentation times, and the
record of who each bulk email reached. Their tables kept the names they had
in grading, where they began."""
import uuid

from django.conf import settings
from django.db import models


class SingletonModel(models.Model):
    """Constrain a table to a single row (pk=1) — used for global settings."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class MarksRelease(SingletonModel):
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marks_releases",
    )

    class Meta:
        db_table = "marks_release"

    def __str__(self):
        return f"MarksRelease(released_at={self.released_at})"


class CertificatesRelease(SingletonModel):
    """Gate for participation-certificate downloads, separate from marks.

    Certificates can go out on a different day than grades (e.g. certificates
    at the ceremony, marks a week later), so each has its own toggle.
    """

    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates_releases",
    )
    # Finalist teams get merit certificates handed out separately, so admins
    # can keep their participation certificates locked while releasing to
    # everyone else.
    # Ticked by default: finalist teams get merit certificates through their
    # own channel, so holding them out of the bulk release is the safe norm.
    exclude_finalists = models.BooleanField(default=True)

    class Meta:
        db_table = "certificates_release"

    def __str__(self):
        return f"CertificatesRelease(released_at={self.released_at})"


def template_upload_to(instance, filename):
    """Each uploaded template in a folder of its own, so the file keeps the
    name it was uploaded with. In one shared folder a re-upload of the same
    name collides with the file it replaces (deleted only after the save),
    and storage renames it, e.g. to "BTF_Marks_Release_Template_FSXLa9F.docx"."""
    return f"grading/templates/{uuid.uuid4().hex[:12]}/{filename}"


class GradingSettings(SingletonModel):
    director_1_name = models.CharField(max_length=255, blank=True)
    # The title printed under the name, e.g. "Chair" or "Co-Chair".
    director_1_position = models.CharField(max_length=255, blank=True)
    director_1_signature = models.FileField(upload_to="grading/signatures/", blank=True, null=True)
    director_2_name = models.CharField(max_length=255, blank=True)
    director_2_position = models.CharField(max_length=255, blank=True)
    director_2_signature = models.FileField(upload_to="grading/signatures/", blank=True, null=True)
    marks_summary_template = models.FileField(upload_to=template_upload_to, blank=True, null=True)
    certificate_template = models.FileField(upload_to=template_upload_to, blank=True, null=True)
    mentor_certificate_template = models.FileField(upload_to=template_upload_to, blank=True, null=True)
    # Component code (e.g. "POSTER") -> weight (0..1). Sum should be 1.0 when set.
    component_weights = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "grading_settings"

    def __str__(self):
        return "GradingSettings"


class OutcomeAnnouncement(models.Model):
    """The in-app announcement that goes with one of the emails telling
    groups their Challenge outcome (finalist, non-finalist, non-submission,
    and the results emails to groups and to supervisors), posted from that
    email's page to whoever it has reached (see
    ``services.outcome_announcement``). Its wording is the email's until
    edited; the announcement it last posted is updated when it's posted
    again."""

    # Which email's: a key of ``services.outcome_announcement.KINDS``.
    key = models.CharField(max_length=32, unique=True)
    # The edited wording; unused until ``edited_at`` is set.
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    announcement = models.ForeignKey(
        "announcements.Announcement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "outcome_announcement"


class FinalistEmailSettings(SingletonModel):
    """The details the finalist email gives teams about the Symposium, set on
    the Notify Finalists page each year. Nothing is sent until all are set."""

    symposium_date = models.DateField(null=True, blank=True)
    confirm_by = models.DateField(null=True, blank=True)
    slides_due = models.DateField(null=True, blank=True)
    # Starts empty: each year's link is entered, so last year's never goes out.
    registration_url = models.URLField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "finalist_email_settings"

    def __str__(self):
        return "FinalistEmailSettings"

    @property
    def is_complete(self) -> bool:
        return bool(
            self.symposium_date and self.confirm_by and self.slides_due and self.registration_url
        )

    DATE_FIELDS = ("symposium_date", "confirm_by", "slides_due")

    def dates_before(self, today) -> list[str]:
        """The date fields set to a day before ``today`` (last year's, say)."""
        return [name for name in self.DATE_FIELDS if (day := getattr(self, name)) and day < today]


class PresentationSettings(SingletonModel):
    """Whether finalists see this year's presentation times to give their
    availability. Off until the times are final, so teams only ever pick
    from the real ones."""

    times_shown = models.BooleanField(default=False)

    class Meta:
        db_table = "presentation_settings"


class PresentationSlot(models.Model):
    """A time finalists can present at the Symposium, on the Symposium date
    set on Notify Finalists. Admins set them on the Finalist Presentation
    tab; each year has its own, since the times change year to year. Each
    finalist team ticks every slot it can make."""

    year = models.PositiveSmallIntegerField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "presentation_slot"
        ordering = ["year", "starts_at", "ends_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "starts_at", "ends_at"], name="uniq_presentation_slot_per_year"
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="presentation_slot_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        return f"{self.year} {self.starts_at:%H:%M}-{self.ends_at:%H:%M}"


class PresentationAllocation(models.Model):
    """The time a finalist team presents at the Symposium, given on the
    Finalist Presentation tab. It goes when the team stops being a finalist
    or the time is removed. Several teams may share a time."""

    flag = models.OneToOneField(
        "grading.FinalistFlag", on_delete=models.CASCADE, related_name="presentation_allocation"
    )
    slot = models.ForeignKey(PresentationSlot, on_delete=models.CASCADE, related_name="allocations")

    class Meta:
        db_table = "presentation_allocation"

    def __str__(self):
        return f"{self.flag_id}: {self.slot_id}"


class PresentationAvailability(models.Model):
    """A finalist team's answer: every presentation time the team can make.
    Anyone on the team (students, mentors, supervisors) or an admin submits
    it for the whole team. Until ``submitted_at`` is set the team hasn't
    answered: its times are only carried over from before, when each student
    answered for themselves."""

    group = models.OneToOneField(
        "groups.Groups", on_delete=models.CASCADE, related_name="presentation_availability"
    )
    # A removed time drops out of every answer.
    slots = models.ManyToManyField(PresentationSlot, blank=True, related_name="available")
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "presentation_availability"

    def __str__(self):
        return f"{self.group_id}"


class FinalistSlides(models.Model):
    """A finalist team's slide deck for its Symposium presentation, due on
    the slides due date set on Notify Finalists. One per team; uploading
    again replaces it."""

    group = models.OneToOneField(
        "groups.Groups", on_delete=models.CASCADE, related_name="finalist_slides"
    )
    # As a submission's files: {"storage_key", "name", "mime", "size"}.
    file = models.JSONField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalist_slides",
    )
    submitted_at = models.DateTimeField()

    class Meta:
        db_table = "finalist_slides"

    def __str__(self):
        return f"{self.group_id}: {self.file.get('name', '')}"


class ResultsEmailSettings(SingletonModel):
    """What the results emails tell teams about the feedback survey, set on
    the Release Results tab each year. Nothing is sent until both are set."""

    # Starts empty: each year's survey is entered, so last year's never goes out.
    survey_url = models.URLField(max_length=500, blank=True)
    survey_closes = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "results_email_settings"

    def __str__(self):
        return "ResultsEmailSettings"

    @property
    def is_complete(self) -> bool:
        return bool(self.survey_url and self.survey_closes)


class EmailDelivery(models.Model):
    """One person a team's bulk email reached: the finalist, non-finalist,
    non-submission or group results email (``email``, the run's key). A team
    is only recorded as emailed once everyone on it has the email; these let a
    retry email just the people a run missed, so nobody gets a second copy."""

    email = models.CharField(max_length=64)
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE, related_name="+")
    address = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_delivery"
        constraints = [
            models.UniqueConstraint(fields=["email", "group", "address"], name="uniq_email_delivery"),
        ]

    def __str__(self):
        return f"{self.email}: {self.group_id} {self.address}"


class EmailSendRun(models.Model):
    """One bulk email's send (Notify Finalists, Notify Nonfinalist, Release
    Results): the run going now, or the last one. Pressing Send queues a run on
    the server that emails everyone due, whether or not the page stays open.
    One run at a time across every email: ``held_until`` is a lease the run
    renews as it goes, so one that dies frees it once it passes. One row per
    email, made on first use, and one more that holds the queue while it
    sends; see ``services.send_guard``."""

    key = models.CharField(max_length=64, unique=True)
    held_until = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    finished_at = models.DateTimeField(null=True, blank=True)
    # People due the email when the run started, and those emailed so far.
    due = models.PositiveIntegerField(default=0)
    emailed = models.PositiveIntegerField(default=0)
    # Teams or supervisors not emailed in full: the next run tries them again.
    failed = models.PositiveIntegerField(default=0)
    # Why the run stopped short, e.g. the mail server couldn't be reached.
    error = models.CharField(max_length=300, blank=True)
    # Who it couldn't reach and why, as the page lists them:
    # {"who": "(BTF07) Amy Chen", "reason": "address refused"}.
    missed = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "email_send_run"

    def __str__(self):
        return f"EmailSendRun({self.key})"


class QueuedEmailSend(models.Model):
    """A bulk email send waiting its turn: one starts only once the one
    before it has finished. Who it emails is worked out when it starts (see
    ``services.send_guard``)."""

    key = models.CharField(max_length=64)
    # What the press asked for, e.g. {"which": "missed"}.
    options = models.JSONField(default=dict, blank=True)
    queued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    queued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_send_queue"
        ordering = ["id"]

    def __str__(self):
        return f"QueuedEmailSend({self.key})"


class ResultsTeamEmail(models.Model):
    """A team emailed about its results; sending skips it after that. Only
    recorded once every member got the email, so a retry reaches the rest."""

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="results_email",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "results_team_email"

    def __str__(self):
        return f"Results emailed: {self.group}"


class ResultsSupervisorEmail(models.Model):
    """A supervisor emailed about their students' results for a year."""

    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    year = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "results_supervisor_email"
        constraints = [
            models.UniqueConstraint(
                fields=["supervisor", "year"],
                name="unique_results_email_per_supervisor_year",
            ),
        ]

    def __str__(self):
        return f"Results emailed: supervisor {self.supervisor_id} ({self.year})"


class NonFinalistEmail(models.Model):
    """A team that wasn't picked, emailed the invitation to the Symposium from
    Notify Nonfinalist; sending skips it after that. Only recorded once every
    member got the email, so a retry reaches the rest."""

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="nonfinalist_email",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "nonfinalist_email"

    def __str__(self):
        return f"Non-finalist emailed: {self.group}"


class NonSubmissionEmail(models.Model):
    """A team that didn't submit, emailed the notice (and invitation to the
    Symposium) from Notify Nonfinalist; sending skips it after that. Only
    recorded once every member got the email, so a retry reaches the rest."""

    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="nonsubmission_email",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "nonsubmission_email"

    def __str__(self):
        return f"Non-submission emailed: {self.group}"
