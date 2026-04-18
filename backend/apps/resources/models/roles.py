from django.db import models
from django.db.models import Q


class Roles(models.Model):
    slug = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "roles"
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        constraints = [
            models.CheckConstraint(
                condition=~Q(slug=""),
                name="roles_slug_not_empty",
            ),
        ]

    def __str__(self):
        return self.slug
