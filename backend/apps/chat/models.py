# CHAT MODELS

from django.db import models

class MessageAttachments(models.Model):
    pk = models.CompositePrimaryKey('attachment_id', 'message_id')
    attachment_id = models.BigIntegerField()
    message = models.ForeignKey('Messages', models.DO_NOTHING)
    attachment_filename = models.CharField(max_length=255)

    class Meta:
        db_table = 'message_attachments'

class Messages(models.Model):
    message_id = models.BigIntegerField(primary_key=True)
    sender_user = models.ForeignKey('Users', models.DO_NOTHING)
    group = models.ForeignKey(Groups, models.DO_NOTHING)
    message_text = models.CharField(max_length=255)
    sent_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()

    class Meta:
        db_table = 'messages'