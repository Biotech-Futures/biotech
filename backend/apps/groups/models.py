# GROUPS MODELS
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import timedelta
from django.core.exceptions import ValidationError 
import uuid

def get_current_year():
    return timezone.now().year

class Groups(models.Model):
    group_number = models.CharField(max_length=50, # to hold something that comes from qualtrics like R_49n3r8XlHkOmYKJ_1
                                           unique=True, 
                                           null=False, 
                                           blank=False,
                                           default="UNSPECIFIED"
                                           )
    group_name = models.CharField(blank=False, null=False, max_length=255, 
                                  validators=[RegexValidator(r'^[A-Za-z0-9 _-]+$', 'Only letters, numbers, spaces, underscores, and hyphens allowed.')], 
                                  error_messages={'blank': 'Group name cannot be blank.'},
                                  help_text="Name of Group (must not be empty)")
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT) # Protect to prevent deletion when referenced track is gone 
    # I thought this might be good just in case tracks are deleted but groups should persist in the instance tracks are moved or removed
    cohort_year = models.IntegerField(blank=False, null=False, default=get_current_year, db_index=True, help_text="Group Cohort Year (e.g. 2025)")
    # cohort field created for yearly group cycles
    creation_datetime = models.DateTimeField(default=timezone.now) # Default to current time on creation
    deleted_flag = models.BooleanField(default=False) # Default to False for better data integrity
    deleted_datetime = models.DateTimeField(null=True, blank=True) # Allow null/blank for groups that aren't deleted

    class Meta:
        db_table = 'groups'
        indexes = [
        models.Index(fields=['creation_datetime']),
        models.Index(fields=['track', 'cohort_year'])
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
            # Ensure group names are unique within the same track, cohort and check if deleted (e.g. if active)
            # means a new group can take the same name as a deleted one
            models.UniqueConstraint(
                fields=['track', 'group_name', 'cohort_year'],
                condition=Q(deleted_flag=False),
                name='unique_ACTIVE_group_name_per_track_cohort'
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
        ]

    
    def save(self, *args, **kwargs):
        # ensure that creation datetime is set on first save
        if self.creation_datetime is None:
            self.creation_datetime = timezone.now()
        # tiny grace window to avoid clock jitter
        skew = timedelta(seconds=1)
        now = timezone.now()
        if self.creation_datetime > now + skew:
            raise ValidationError({"creation_datetime": f"cannot be in future - DB: {now}, attempted: {self.creation_datetime}"})
        # ensure a unique group_number is assigned if unspecified
        if not self.group_number or str(self.group_number).strip() == "" or self.group_number == "UNSPECIFIED":
            # generate a stable unique token
            # keep it short but unique enough for our scale
            for _ in range(5):
                candidate = f"AUTO-{uuid.uuid4().hex[:12]}"
                if not Groups.objects.filter(group_number=candidate).exists():
                    self.group_number = candidate
                    break
            else:
                raise ValidationError({"group_number": "Could not generate a unique group_number. Please retry."})
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.group_name

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
    country_name_SHORT_FORM = models.CharField(max_length=3, default="___")

    class Meta:
        db_table = 'countries'
        indexes = [
            models.Index(fields=['country_name'])
        ]

    def __str__(self):
        return self.country_name


class CountryStates(models.Model):
    country = models.ForeignKey('Countries', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by country
    state_name = models.CharField(max_length=255)
    state_name_SHORT_FORM = models.CharField(max_length=3, default="___")

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