from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.matching_weights import (
    REQUIRED_WEIGHT_TOTAL,
    WEIGHT_FIELDS,
    ScoringWeights,
    weights_from_config,
)


class MatchRun(models.Model):
    class RunTypeChoices(models.TextChoices):
        AUTO = "auto", "Automatic"
        MANUAL = "manual", "Manual"
        RERUN = "rerun", "Re-run"

    initiated_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    run_type = models.CharField(max_length=100, choices=RunTypeChoices.choices)
    rules_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "match_run"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["initiated_by_user"]),
            models.Index(fields=["run_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.run_type} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class MatchRecommendation(models.Model):
    match_run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="recommendations")
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    mentor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    explanation = models.JSONField(null=True, blank=True)
    accepted = models.BooleanField(default=False)

    class Meta:
        db_table = "match_recommendation"
        indexes = [
            models.Index(fields=["match_run"]),
            models.Index(fields=["group"]),
            models.Index(fields=["mentor_user"]),
            models.Index(fields=["accepted"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["match_run", "group", "mentor_user"],
                name="unique_match_recommendation_per_run_group_mentor",
            ),
        ]

    def __str__(self):
        return f"Run {self.match_run_id} -> group {self.group_id} / mentor {self.mentor_user_id}"


class MatchingConfig(models.Model):
    """Admin-tunable scoring weights for the matching algorithms (MA1).

    Weights are percentages of the 100-point base score and must total exactly
    100 — see ``apps.common.matching_weights``. The values are read once per
    matching run and snapshotted onto ``MatchRun.rules_snapshot``, so changing
    them never rewrites the rules a past run was scored under. Country is not
    among them: it stopped scoring in MA4 and only ranks ties via its count.

    At most one row is active; :meth:`activate` retires the previous one.
    """

    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    year_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Percentage of the base score charged per year of year-level gap.",
    )
    timezone_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Percentage of the base score charged per hour of timezone gap.",
    )
    timezone_max_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Cap on the timezone penalty, as a percentage of the base score.",
    )
    size_bonus_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Bonus for a full-sized group, as a percentage of the base score.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matching_configs",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matching_config"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name

    @property
    def total_weight(self) -> Decimal:
        # ``Decimal(str(value))`` because an unsaved instance (admin form data,
        # serializer validation) can still hold the raw string a client sent.
        total = Decimal("0")
        for field_name, _ in WEIGHT_FIELDS:
            value = getattr(self, field_name, None)
            if value is not None:
                total += Decimal(str(value))
        return total

    def weight_total_error(self) -> Optional[str]:
        """Validation message for the 100% rule, or ``None`` when it holds.

        Shared by ``clean()`` and the API serializer so both reject a config the
        same way. Values are never normalised: an admin who mistypes a weight is
        told the total, not silently corrected.
        """
        required = Decimal(REQUIRED_WEIGHT_TOTAL)
        total = self.total_weight
        if total == required:
            return None
        shortfall = required - total
        direction = "under" if shortfall > 0 else "over"
        return (
            f"Matching weights must total exactly {REQUIRED_WEIGHT_TOTAL}% "
            f"(currently {total}%, {abs(shortfall)}% {direction})."
        )

    def clean(self):
        super().clean()
        error = self.weight_total_error()
        if error:
            raise ValidationError({"weight_total": error})

    def to_scoring_weights(self) -> ScoringWeights:
        return weights_from_config(self)

    def activate(self, *, commit: bool = True) -> None:
        """Make this the single active config, retiring any previous one."""
        now = timezone.now()
        MatchingConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(
            is_active=False,
            updated_at=now,
        )
        self.is_active = True
        if commit:
            self.save(update_fields=["is_active", "updated_at"])

    @classmethod
    def get_active(cls) -> Optional["MatchingConfig"]:
        return cls.objects.filter(is_active=True).order_by("-updated_at", "-id").first()

