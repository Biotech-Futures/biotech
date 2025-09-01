# CHAT MODELS

from django.db import models

class MessageAttachments(models.Model):
    pk = models.CompositePrimaryKey('attachment_id', 'message_id')
    attachment_id = models.BigIntegerField()
    message_id = models.BigIntegerField(unique=True)
    attachment_filename = models.CharField(max_length=255)

    class Meta:
        # managed = False
        db_table = 'message_attachments'


class Messages(models.Model):
    message = models.OneToOneField(MessageAttachments, models.DO_NOTHING, primary_key=True)
    sender_user_id_fk_field = models.ForeignKey('Users', models.DO_NOTHING, db_column='sender_user_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    group_id_fk_field = models.ForeignKey(Groups, models.DO_NOTHING, db_column='group_id (FK)')  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    message_text = models.CharField(max_length=255)
    sent_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'messages'