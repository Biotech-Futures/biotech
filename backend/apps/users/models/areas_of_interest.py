from django.db import models

class AreasOfInterest(models.Model):
    interest_desc = models.CharField(max_length=255)

    class Meta:
        db_table = 'areas_of_interest'
        verbose_name = "Area of Interest"
        verbose_name_plural = "Areas of Interest"

    def __str__(self):
        return self.interest_desc
