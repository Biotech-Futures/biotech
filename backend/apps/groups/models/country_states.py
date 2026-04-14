from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class CountryStates(models.Model):
    country = models.ForeignKey('Countries', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by country
    state_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'country_states'
        constraints = [
            models.UniqueConstraint(fields=['country', 'state_name'], name='unique_state_per_country')
        ]

    def __str__(self):
        return f"{self.state_name}, {self.country.country_name}"
