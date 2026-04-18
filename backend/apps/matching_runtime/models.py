from django.conf import settings
from django.db import models
from django.utils import timezone


class MatchRun(models.Model):
    initiated_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True)
    run_type = models.CharField(max_length=100)
    rules_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "match_run"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["initiated_by_user"]),
            models.Index(fields=["track"]),
            models.Index(fields=["run_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.run_type} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class MatchRecommendation(models.Model):
    match_run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="recommendations")
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    mentor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
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

