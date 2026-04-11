# GROUPS MODELS
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

class Groups(models.Model):
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT) # Protect to prevent deletion when referenced track is gone 
    # I thought this might be good just in case tracks are deleted but groups should persist in the instance tracks are moved or removed
    creation_datetime = models.DateTimeField(default=timezone.now) # Default to current time on creation
    deleted_flag = models.BooleanField(default=False) # Default to False for better data integrity
    deleted_datetime = models.DateTimeField(null=True, blank=True) # Allow null/blank for groups that aren't deleted
    # Refined schema (table_statements.sql): matching / cohort fields
    year_min = models.PositiveSmallIntegerField(null=True, blank=True)
    year_max = models.PositiveSmallIntegerField(null=True, blank=True)
    lead_mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_groups",
    )
    max_members = models.PositiveSmallIntegerField(default=8, null=True, blank=True)

    class Meta:
        db_table = 'groups'
        indexes = [
        models.Index(fields=['track']),
        models.Index(fields=['deleted_flag']),
        models.Index(fields=['creation_datetime']),
        models.Index(fields=['lead_mentor']),
        ]

        constraints = [
            # Ensure deleted_flag is True if deleted_datetime is set
            models.CheckConstraint(
                condition=(
                    (Q(deleted_flag=True)  & Q(deleted_datetime__isnull=False)) |
                    (Q(deleted_flag=False) & Q(deleted_datetime__isnull=True))
                ),
                name='group_deleted_flag_datetime_consistent',
            ),
            # Ensure group names are unique within the same track
            models.UniqueConstraint(
                fields=['track', 'group_name'],
                name='unique_group_name_per_track'
            ),
            # Ensure deleted_datetime is after creation_datetime if set
            models.CheckConstraint(
                condition=Q(deleted_datetime__gte=F('creation_datetime')) | Q(deleted_datetime__isnull=True),
                name='deleted_after_creation'
            ),
            # Ensure group_name is not empty
            # models.CheckConstraint(
            #     condition=Length(Trim('group_name')) > 0,
            #     name='group_name_not_empty'
            # ),
            ##### Replaced the problematic constraint with:
            models.CheckConstraint(
                check=~Q(group_name__regex=r'^\s*$'),
                name='group_name_not_empty'
            ),
            # Ensure creation_datetime is not in the future
            models.CheckConstraint(
                condition=Q(creation_datetime__lte=models.functions.Now()),
                name='group_creation_not_future'
            ),
            models.CheckConstraint(
                condition=Q(year_min__isnull=True)
                | Q(year_max__isnull=True)
                | Q(year_min__lte=F("year_max")),
                name="groups_year_range_valid",
            ),
        ]
    
    def __str__(self):
        return self.group_name


class GroupInterest(models.Model):
    """Junction: group-level interests for matching (refined DDL: group_interest)."""

    group = models.ForeignKey("Groups", on_delete=models.CASCADE, related_name="group_interests")
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
        return f"{self.group_id}:{self.interest_id}"


class GroupMembers(models.Model):
    group = models.ForeignKey('Groups', models.CASCADE) # thinking cascade since if a group is deleted, members should be removed from that group
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE) # Cascade to remove user from group if user is deleted
    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'user'],
                name='unique_group_user'
            )
            # TODO: implement some sort of constraint or check which only allows a user to be added to an active (not deleted) group
        ] # Composite unique constraint to ensure each user is unique per group, as composite keys aren't natively supported
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user} in {self.group}"
    

class Countries(models.Model):
    country_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'countries'
        indexes = [
            models.Index(fields=['country_name']),
        ]

    def __str__(self):
        return self.country_name


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

class Tracks(models.Model):
    track_name = models.CharField(unique=True, max_length=255)
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by groups

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['track_name']),
        ]

    def __str__(self):
        return self.track_name
    
    #  COMMENTS
    #  Still a bit unsrure about the structure here, tracks and states are almost the same thing?
    #  Maybe we could have tracks as the 'countries' or region as 'state' or something similar like how CountryStates is structured 
    #   - this would remove the double up in similar tables and make it a bit clearer