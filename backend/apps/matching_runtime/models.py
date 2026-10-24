from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.matching_weights import (
    MAX_TOTAL_PENALTY,
    PENALTY_CAP_FIELDS,
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

    Weights are raw points off the 100-point base score, under no obligation
    to total anything — see ``apps.common.matching_weights``. What is enforced
    is the penalty ceiling: the two caps may not together exceed the base
    score, or the worst pairings all bottom out at zero and stop being
    rankable. The values are read once per matching run and snapshotted onto
    ``MatchRun.rules_snapshot``, so changing them never rewrites the rules a
    past run was scored under. Country is not among them: it stopped scoring in
    MA4 and only ranks ties via its count.

    There is exactly one config, ever: saving a new row replaces the stored
    one, so :meth:`get_singleton` is never ambiguous. The run snapshot freezes
    the weights themselves, so editing the row never rewrites what a past run
    was scored under.
    """

    year_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Points charged per year of year-level gap between two students.",
    )
    year_max_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Cap on the year penalty, in points, however far apart two students are.",
    )
    timezone_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Points charged per hour of timezone gap between two students.",
    )
    timezone_max_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Cap on the timezone penalty, in points, however far apart two students are.",
    )
    size_bonus_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Points added for forming a full-sized group.",
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
        return f"Scoring config #{self.pk}"

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

    @property
    def max_total_penalty(self) -> Decimal:
        """The most the penalties can take off a score, both caps binding."""
        total = Decimal("0")
        for field_name, _ in PENALTY_CAP_FIELDS:
            value = getattr(self, field_name, None)
            if value is not None:
                total += Decimal(str(value))
        return total

    def penalty_ceiling_error(self) -> Optional[str]:
        """Validation message for the penalty ceiling, or ``None`` when it holds.

        Weights are raw points and may total anything, so there is no budget to
        police. The one thing that does break scoring is penalties big enough to
        wipe out the whole base score: past that, every distant pairing floors
        at zero and the algorithm can no longer rank one above another. Only the
        caps are counted, because they bound what the per-unit weights can
        actually charge.

        Shared by ``clean()`` and the API serializer so both reject a config the
        same way. Values are never normalised: an admin who sets the caps too
        high is told by how much, not silently corrected.
        """
        ceiling = Decimal(str(MAX_TOTAL_PENALTY))
        total = self.max_total_penalty
        if total <= ceiling:
            return None
        return (
            f"Please lower a cap by at least {total - ceiling}, otherwise the "
            f"worst pairing would fall below 0 — the caps total {total} against "
            f"a {ceiling}-point score."
        )

    def clean(self):
        super().clean()
        error = self.penalty_ceiling_error()
        if error:
            raise ValidationError({"penalty_ceiling": error})

    def to_scoring_weights(self) -> ScoringWeights:
        return weights_from_config(self)

    def save(self, *args, **kwargs):
        # A config is a singleton: inserting a new row replaces the previous
        # one so ``get_singleton()`` stays unambiguous.
        if self._state.adding:
            type(self).objects.exclude(pk=self.pk).delete()
        super().save(*args, **kwargs)

    @classmethod
    def get_singleton(cls) -> Optional["MatchingConfig"]:
        """The one stored config, or ``None`` when none has been saved yet."""
        return cls.objects.first()

