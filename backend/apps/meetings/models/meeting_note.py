from django.db import models


class MeetingNote(models.Model):
    meeting = models.OneToOneField("GroupMeeting",on_delete=models.CASCADE,related_name="note")
    body = models.TextField()
    revision = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(on_delete=models.SET_NULL,null=True)#   wwwwww
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meeting_note'

    def __str__(self):
        return self.meeting.event.title