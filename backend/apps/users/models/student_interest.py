from django.db import models


class StudentInterest(models.Model):
    interest = models.ForeignKey("AreasOfInterest", on_delete=models.CASCADE)
    student_profile = models.ForeignKey(
        "StudentProfile",
        on_delete=models.CASCADE,
        db_column="student_user_id",
        related_name="interests",
    )

    class Meta:
        db_table = "student_interest"
        verbose_name = "Student Interest"
        verbose_name_plural = "Student Interests"
        constraints = [
            models.UniqueConstraint(
                fields=["interest", "student_profile"],
                name="pk_student_interest",
            ),
        ]
        indexes = [
            models.Index(fields=["student_profile"]),
            models.Index(fields=["interest"]),
        ]

    def __str__(self):
        return f"{self.student_profile.user} interested in {self.interest}"
