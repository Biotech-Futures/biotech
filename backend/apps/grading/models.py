from django.conf import settings
from django.db import models


class SubmissionComponent(models.Model):
    """The gradeable parts of a team's entry (SAQ / POSTER / REPORT / PROTOTYPE).

    Owned by grading as pure marking configuration: it says what rubrics attach
    to, not where student work lives. The student portal stores an entry as one
    row with per-slot fields; ``services.content`` translates that row into
    per-component views keyed by this catalogue's codes.
    """

    code = models.CharField(unique=True, max_length=32)
    name = models.CharField(max_length=255)
    is_optional = models.BooleanField(default=False)
    accepts_file = models.BooleanField(default=True)
    accepts_text = models.BooleanField(default=False)
    accepts_link = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "grading_component"
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name


class Rubric(models.Model):
    component = models.ForeignKey(
        SubmissionComponent,
        on_delete=models.PROTECT,
        related_name="rubrics",
    )
    year = models.PositiveIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "rubric"
        constraints = [
            models.UniqueConstraint(
                fields=["component", "year"],
                name="unique_rubric_per_component_year",
            ),
        ]
        indexes = [
            models.Index(fields=["component", "year"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return f"{self.component.code} {self.year}"


class RubricCriterion(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name="criteria")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    max_mark = models.DecimalField(max_digits=6, decimal_places=2)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "rubric_criterion"
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["rubric", "order"]),
        ]

    def __str__(self):
        return f"{self.rubric} — {self.name}"


class Grade(models.Model):
    # One submission row now covers a group's whole entry (all components), so
    # a single submission id carries grades for every component. The pair
    # (submission, criterion) is still exact: a criterion belongs to exactly
    # one rubric, and a rubric to exactly one component. Any per-component
    # aggregation must therefore filter via criterion__rubric__component,
    # never assume the submission implies a component.
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="grades",
    )
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.PROTECT, related_name="grades")
    mark = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grades",
    )
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "grade"
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "criterion"],
                name="unique_grade_per_submission_criterion",
            ),
        ]
        indexes = [
            models.Index(fields=["submission", "criterion"]),
            models.Index(fields=["graded_at"]),
        ]

    def __str__(self):
        return f"{self.submission} — {self.criterion.name}: {self.mark}"


class ComponentFeedback(models.Model):
    """Marker's overall comment on one component of a group's entry.

    Used to live as ``overall_comment`` on the per-component submission row.
    With one submission row per group that column can't hold four comments, so
    the comment is keyed (group, component) here instead — a key that is
    independent of how the submissions app stores the entry. Feeds the marks
    release docx (e.g. the template's "Overall Poster Comment" block).
    """

    group = models.ForeignKey(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="component_feedback",
    )
    component = models.ForeignKey(
        SubmissionComponent,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    comment = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="component_feedback",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "component_feedback"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "component"],
                name="unique_feedback_per_group_component",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "component"]),
        ]

    def __str__(self):
        return f"{self.group} — {self.component.code} feedback"


class FinalistFlag(models.Model):
    group = models.OneToOneField(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="finalist_flag",
    )
    flagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalist_flags",
    )
    flagged_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    # When the notification email actually went out; null until then (and for
    # rows notified before this field existed).
    notified_at = models.DateTimeField(null=True, blank=True)
    notified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalist_notifications",
    )

    class Meta:
        db_table = "finalist_flag"
        indexes = [
            models.Index(fields=["notified"]),
        ]

    def __str__(self):
        return f"Finalist: {self.group}"


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


class GradingSettings(SingletonModel):
    director_1_name = models.CharField(max_length=255, blank=True)
    director_1_signature = models.FileField(upload_to="grading/signatures/", blank=True, null=True)
    director_2_name = models.CharField(max_length=255, blank=True)
    director_2_signature = models.FileField(upload_to="grading/signatures/", blank=True, null=True)
    marks_summary_template = models.FileField(upload_to="grading/templates/", blank=True, null=True)
    certificate_template = models.FileField(upload_to="grading/templates/", blank=True, null=True)
    # Component code (e.g. "POSTER") -> weight (0..1). Sum should be 1.0 when set.
    component_weights = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "grading_settings"

    def __str__(self):
        return "GradingSettings"


class GradingJob(models.Model):
    KIND_BULK_ZIP = "bulk_zip"
    KIND_MARKS_RELEASE = "marks_release"
    KIND_CHOICES = [
        (KIND_BULK_ZIP, "Bulk zip"),
        (KIND_MARKS_RELEASE, "Marks release"),
    ]

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    params = models.JSONField(default=dict, blank=True)
    result_url = models.URLField(max_length=1024, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "grading_job"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["kind", "status"]),
        ]

    def __str__(self):
        return f"{self.kind}#{self.pk} [{self.status}]"
