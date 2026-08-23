from django.db import models

class MeetingSummary(models.Model):
    meeting = models.OneToOneField("GroupMeeting", on_delete=models.CASCADE, related_name="summary")
    summary = models.TextField()
    author = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'meeting_summary'

    def __str__(self):
        return self.meeting.event.title