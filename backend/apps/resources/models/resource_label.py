from django.db import models


class ResourceLabel(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        db_table = "resource_labels"
        ordering = ["name"]
        verbose_name = "Resource Label"
        verbose_name_plural = "Resource Labels"

    def __str__(self):
        return self.name
