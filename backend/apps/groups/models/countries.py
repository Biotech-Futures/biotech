from django.db import models

class Countries(models.Model):
    country_name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'countries'

    def __str__(self):
        return self.country_name
