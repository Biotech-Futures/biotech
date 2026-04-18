from django.db import models
from django.db.models import F, Q


class MentorAvailability(models.Model):
    mentor_profile = models.ForeignKey(
        "MentorProfile",
        on_delete=models.CASCADE,
        db_column="mentor_user_id",
        related_name="availabilities",
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = "mentor_availability"
        verbose_name = "Mentor Availability"
        verbose_name_plural = "Mentor Availability"
        constraints = [
            models.UniqueConstraint(
                fields=["mentor_profile", "weekday", "start_time", "end_time"],
                name="unique_mentor_availability_slot",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="mentor_availability_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="mentor_availability_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["mentor_profile"]),
            models.Index(fields=["weekday"]),
        ]

    def __str__(self):
        return f"{self.mentor_profile.user} on {self.weekday} from {self.start_time} to {self.end_time}"
