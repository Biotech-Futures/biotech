from django.db import models, transaction


class Tracks(models.Model):
    track_name = models.CharField(unique=True, max_length=100)
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return self.track_name

    def save(self, *args, **kwargs):
        # Detect is_archived False → True transition and force-logout
        # non-admin members on commit, so a rolled-back archive doesn't
        # leave anyone stranded as logged-out.
        was_archived = (
            Tracks.objects.filter(pk=self.pk)
            .values_list("is_archived", flat=True)
            .first()
            if self.pk
            else None
        )
        super().save(*args, **kwargs)
        if was_archived is False and self.is_archived:
            from apps.users.utils.track_gate import revoke_sessions_for_archived_track
            transaction.on_commit(lambda: revoke_sessions_for_archived_track(self))
