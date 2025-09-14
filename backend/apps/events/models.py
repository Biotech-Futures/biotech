# EVENTS MODELS
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

class EventInvite(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # changed to CASCADE to maintain referential integrity
    sent_datetime = models.DateTimeField(default=timezone.now)
    attendance_status = models.BooleanField(default=False) # changed to default False to avoid null values
    rsvp_status = models.BooleanField(default=False) # changed to default False to avoid null values

    class Meta:
        db_table = 'event_invite'
        verbose_name = "Event Invite"
        verbose_name_plural = "Event Invites"
        constraints = [
            models.UniqueConstraint(fields=['event', 'user'], name='unique_event_user'), # we remove the composite and add this constraint since django will add a default id field and composite keys arent natively supported

            # Ensure attendance can only be True if RSVP is also True
            models.CheckConstraint(
                condition=models.Q(attendance_status=False) | models.Q(rsvp_status=True),
                name='check_attendance_requires_rsvp'
            ),
            models.CheckConstraint(
                condition=models.Q(sent_datetime__lte=models.functions.Now()),
                name='check_invite_sent_datetime_not_future'
            )
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Invite for {self.user} to {self.event}"

class EventTargetGroup(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    group = models.ForeignKey('groups.Groups', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_group'
        verbose_name = "Event Target Group"
        verbose_name_plural = "Event Target Groups"
        constraints = [
            models.UniqueConstraint(fields=['event', 'group'], name='unique_event_group')
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['group']),
        ]
    
    def __str__(self):
        return f"Target Group {self.group} for Event {self.event}"
    

class EventTargetRole(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    role = models.ForeignKey('resources.Roles', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_role'
        verbose_name = "Event Target Role"
        verbose_name_plural = "Event Target Roles"
        constraints = [
            models.UniqueConstraint(fields=['event', 'role'], name='unique_event_role')
        ]

    def __str__(self):
        return f"Target Role {self.role} for Event {self.event}"
        

class EventTargetTrack(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    track = models.ForeignKey('groups.Tracks', on_delete=models.CASCADE)

    class Meta:
        db_table = 'event_target_track'
        verbose_name = "Event Target Track"
        verbose_name_plural = "Event Target Tracks"
        constraints = [
            models.UniqueConstraint(fields=['event', 'track'], name='unique_event_track')
        ]
    
    def __str__(self):
        return f"{self.track} targeted for {self.event}"

class Events(models.Model):
    event_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True) # Allow null/blank for virtual events
    humanitix_link = models.URLField(max_length=255)
    host_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True) # Set null to allow events to persist if host user is deleted
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(default=None, blank=True, null=True) # Allow null/blank for events that aren't deleted
    event_image = models.CharField(db_column='event_image(IMG)', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.     
    is_virtual = models.BooleanField(default=False)

    class Meta:
        db_table = 'events'
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['start_datetime']),
            models.Index(fields=['host_user']),
        ]
        constraints = [
            # Ensure event end is after start
            models.CheckConstraint(
                condition=models.Q(ends_datetime__gt=models.F('start_datetime')),
                name='check_event_end_after_start'
            ),
            # Ensure deleted_flag is True for deleted events and False otherwise
            models.CheckConstraint(
                condition=(
                    models.Q(deleted_flag=False) |
                    (models.Q(deleted_flag=True) & models.Q(deleted_datetime__isnull=False))
                ),
                name='check_deleted_flag_and_datetime'
            ),
            # Ensure virtual events don't have a location 
            models.CheckConstraint(
                condition=models.Q(is_virtual=False) | models.Q(location__isnull=True),
                name='check_virtual_location_null'
            ),
        ]

    def __str__(self):
        return self.event_name