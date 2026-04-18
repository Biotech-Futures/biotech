from django.db import models


class GroupInterest(models.Model):
    group = models.ForeignKey("Groups", on_delete=models.CASCADE, related_name="interests")
    interest = models.ForeignKey(
        "users.AreasOfInterest",
        on_delete=models.CASCADE,
        related_name="group_links",
    )

    class Meta:
        db_table = "group_interest"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "interest"],
                name="unique_group_interest",
            ),
        ]
        indexes = [
            models.Index(fields=["group"]),
            models.Index(fields=["interest"]),
        ]

    def __str__(self):
        return f"{self.group_id} -> {self.interest_id}"
