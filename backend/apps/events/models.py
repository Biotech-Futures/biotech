# EVENTS MODELS

from django.db import models

class EventInvite(models.Model):
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    user = models.ForeignKey('users.Users', on_delete=models.CASCADE) # changed to CASCADE to maintain referential integrity
    sent_datetime = models.DateTimeField()
    attendance_status = models.BooleanField(default=False) # changed to default False to avoid null values
    rsvp_status = models.BooleanField(default=False) # changed to default False to avoid null values

    class Meta:
        db_table = 'event_invite'
        verbose_name = "Event Invite"
        verbose_name_plural = "Event Invites"
        constraints = [
            models.UniqueConstraint(fields=['event', 'user'], name='unique_event_user') # we remove the composite and add this constraint since django will add a default id field and composite keys arent natively supported
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
    event_id = models.BigAutoField(primary_key=True)
    event_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)
    humanitix_link = models.CharField(max_length=255)
    host_user = models.ForeignKey('users.Users', on_delete=models.PROTECT)
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

    def __str__(self):
        return self.event_name