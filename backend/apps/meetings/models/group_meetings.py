from django.db import models

class GroupMeeting(models.Model):
    event = models.OneToOneField("events.Events", on_delete=models.CASCADE,related_name="group_meeting") # modify event, add group meeting
    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="group_meetings")
    organiser = models.ForeignKey(models.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null = True)
    created_at = models.DateTimeField
    class Meta:
        db_table = 'group_meeting'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['group']),
        ]
    def __str__(self):
        return self.event.title
