# Phase 2 migration: upgrades the messages table with lifecycle fields.
# Applies changes in safe order: drop old constraints → alter fields →
# rename fields → add new fields → remove deleted_flag → update indexes
# → add new constraints → create MessageStatus table.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_messageresource_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # Step 1: Remove old constraints that reference fields we are changing
        migrations.RemoveConstraint(
            model_name='messages',
            name='deleted_flag_boolean',
        ),
        migrations.RemoveConstraint(
            model_name='messages',
            name='unique_message_per_user_per_time',
        ),

        # Step 2: Change message_text from CharField(255) to TextField
        migrations.AlterField(
            model_name='messages',
            name='message_text',
            field=models.TextField(blank=True, default=''),
        ),

        # Step 3: Rename sent_datetime to sent_at
        migrations.RenameField(
            model_name='messages',
            old_name='sent_datetime',
            new_name='sent_at',
        ),

        # Step 4: Add new lifecycle fields
        migrations.AddField(
            model_name='messages',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='messages',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Step 5: Add message_type field
        migrations.AddField(
            model_name='messages',
            name='message_type',
            field=models.CharField(
                choices=[
                    ('text', 'Text'),
                    ('attachment', 'Attachment'),
                    ('resource', 'Resource Link'),
                    ('system', 'System Message'),
                ],
                default='text',
                max_length=20,
            ),
        ),

        # Step 6: Remove deleted_flag (data already backfilled to deleted_at)
        migrations.RemoveField(
            model_name='messages',
            name='deleted_flag',
        ),

        # Step 7: Remove old indexes and add new ones
        migrations.AlterIndexTogether(
            name='messages',
            index_together=set(),
        ),
        migrations.AddIndex(
            model_name='messages',
            index=models.Index(fields=['group', 'sent_at'], name='messages_group_sent_idx'),
        ),
        migrations.AddIndex(
            model_name='messages',
            index=models.Index(fields=['sender_user'], name='messages_sender_idx'),
        ),
        migrations.AddIndex(
            model_name='messages',
            index=models.Index(fields=['deleted_at'], name='messages_deleted_at_idx'),
        ),

        # Step 8: Add new lifecycle CheckConstraints
        migrations.AddConstraint(
            model_name='messages',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(deleted_at__isnull=True)
                    | models.Q(deleted_at__gte=models.F('sent_at'))
                ),
                name='message_deleted_after_sent',
            ),
        ),
        migrations.AddConstraint(
            model_name='messages',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(edited_at__isnull=True)
                    | models.Q(edited_at__gte=models.F('sent_at'))
                ),
                name='message_edited_after_sent',
            ),
        ),

        # Step 9: Create MessageStatus table
        migrations.CreateModel(
            name='MessageStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('sent', 'Sent'),
                        ('delivered', 'Delivered'),
                        ('read', 'Read'),
                    ],
                    default='sent',
                    max_length=20,
                )),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('message', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='statuses',
                    to='chat.messages',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='message_statuses',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Message Status',
                'verbose_name_plural': 'Message Statuses',
                'db_table': 'message_status',
            },
        ),
        migrations.AlterUniqueTogether(
            name='messagestatus',
            unique_together={('message', 'user')},
        ),
        migrations.AddIndex(
            model_name='messagestatus',
            index=models.Index(fields=['message'], name='msg_status_message_idx'),
        ),
        migrations.AddIndex(
            model_name='messagestatus',
            index=models.Index(fields=['user', 'status'], name='msg_status_user_status_idx'),
        ),
    ]