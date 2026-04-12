# GROUPS MODELS
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Countries(models.Model):
    country_name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "countries"

    def __str__(self):
        return self.country_name


class CountryStates(models.Model):
    country = models.ForeignKey("Countries", on_delete=models.PROTECT)
    state_name = models.CharField(max_length=255)

    class Meta:
        db_table = "country_states"
        constraints = [
            models.UniqueConstraint(
                fields=["country", "state_name"],
                name="unique_state_per_country",
            )
        ]

    def __str__(self):
        return f"{self.state_name}, {self.country.country_name}"


class Tracks(models.Model):
    track_name = models.CharField(unique=True, max_length=100)
    state = models.ForeignKey("CountryStates", on_delete=models.PROTECT)

    class Meta:
        db_table = "tracks"
        indexes = [
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return self.track_name


class Groups(models.Model):
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey("Tracks", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "groups"
        indexes = [
            models.Index(fields=["track"]),
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["track", "group_name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_group_name_per_track",
            ),
            models.CheckConstraint(
                condition=Q(deleted_at__gte=F("created_at")) | Q(deleted_at__isnull=True),
                name="group_deleted_after_created",
            ),
            models.CheckConstraint(
                condition=~Q(group_name__regex=r"^\s*$"),
                name="group_name_not_empty",
            ),
        ]

    def __str__(self):
        return self.group_name

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class GroupMembership(models.Model):
    group = models.ForeignKey("Groups", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    membership_role = models.CharField(max_length=50, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "group_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                condition=Q(left_at__isnull=True),
                name="unique_active_group_membership",
            ),
            models.CheckConstraint(
                condition=Q(left_at__gte=F("joined_at")) | Q(left_at__isnull=True),
                name="group_membership_left_after_joined",
            ),
        ]
        indexes = [
            models.Index(fields=["group"]),
            models.Index(fields=["user"]),
            models.Index(fields=["left_at"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"
