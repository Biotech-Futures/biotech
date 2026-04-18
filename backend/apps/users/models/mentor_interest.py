from django.db import models


class MentorInterest(models.Model):
<<<<<<< Updated upstream
    mentor_profile = models.ForeignKey(
        "MentorProfile",
        on_delete=models.CASCADE,
        db_column="mentor_user_id",
        related_name="interest_entries",
    )
    interest = models.ForeignKey("AreasOfInterest", on_delete=models.CASCADE)
=======
    mentor_user = models.ForeignKey(
        'MentorProfile', on_delete=models.CASCADE, related_name='interests'
    )
    interest = models.ForeignKey('AreasOfInterest', on_delete=models.CASCADE)
>>>>>>> Stashed changes

    class Meta:
        db_table = "mentor_interest"
        verbose_name = "Mentor Interest"
        verbose_name_plural = "Mentor Interests"
        constraints = [
            models.UniqueConstraint(
                fields=["mentor_profile", "interest"],
                name="unique_mentor_interest",
            ),
        ]
        indexes = [
            models.Index(fields=["mentor_profile"]),
            models.Index(fields=["interest"]),
        ]

    def __str__(self):
        return f"{self.mentor_profile.user} interested in {self.interest}"
