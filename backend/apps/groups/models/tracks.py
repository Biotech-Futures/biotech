from django.db import models


class Tracks(models.Model):
    track_code = models.CharField(unique=True, max_length=100)
<<<<<<< Updated upstream
    state = models.ForeignKey("CountryStates", on_delete=models.PROTECT)
=======
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT)
>>>>>>> Stashed changes

    class Meta:
        db_table = "tracks"
        indexes = [
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return self.track_code
