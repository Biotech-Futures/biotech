import logging

from celery import shared_task

from apps.chat.models import MessageStatus, Messages
from apps.groups.models import GroupMembership

logger = logging.getLogger(__name__)


def enqueue_process_chat_message_created(message_id):
    """
    Queue non-blocking side effects for a newly-created chat message.

    For Celery newcomers: `.delay(...)` does not execute the task inline. It serializes a small
    job payload onto the configured broker (Redis in this project), and a separate Celery worker
    process picks the job up later.
    """
    try:
        process_chat_message_created.delay(message_id)
        return True
    except Exception:
        # Side effects must never break persistence or websocket delivery.
        logger.exception(
            "Failed to enqueue chat message created side effects for message %s",
            message_id,
        )
        return False


@shared_task(name="chat.process_chat_message_created")
def process_chat_message_created(message_id):
    # Celery tasks should always re-load database state by ID instead of trusting in-memory
    # objects from the caller. That keeps the task serializable and safe across processes.
    try:
        message = Messages.objects.select_related("sender_user", "group").get(pk=message_id)
    except Messages.DoesNotExist:
        logger.warning(
            "Chat message %s no longer exists; skipping created side effects.",
            message_id,
        )
        return {
            "status": "missing",
            "message_id": message_id,
            "recipient_ids": [],
            "created_status_count": 0,
            "existing_status_count": 0,
        }

    if message.deleted_at is not None:
        logger.info(
            "Chat message %s is deleted; skipping created side effects.",
            message.id,
        )
        return {
            "status": "skipped_deleted",
            "message_id": message.id,
            "recipient_ids": [],
            "created_status_count": 0,
            "existing_status_count": 0,
        }

    recipient_memberships = list(
        GroupMembership.objects.filter(
            group_id=message.group_id,
            left_at__isnull=True,
        )
        .exclude(user_id=message.sender_user_id)
        .select_related("user")
        .order_by("user_id")
    )

    created_recipient_ids = []
    existing_recipient_ids = []
    notification_hooks = []

    # The task currently prepares hook data and recipient state only. Real delivery integrations
    # (email, push, etc.) can plug in later without changing websocket delivery semantics.
    for membership in recipient_memberships:
        notification_hooks.append(
            {
                "user_id": membership.user_id,
                "email": getattr(membership.user, "email", "") or None,
            }
        )
        # get_or_create keeps the task safe to retry or re-run without duplicating
        # per-recipient state for the same message.
        _, created = MessageStatus.objects.get_or_create(
            message=message,
            user_id=membership.user_id,
            defaults={"status": MessageStatus.StatusChoices.SENT},
        )
        if created:
            created_recipient_ids.append(membership.user_id)
        else:
            existing_recipient_ids.append(membership.user_id)

    # Logging the prepared recipients makes it easier to debug worker behavior without needing a
    # real downstream notification service in development.
    logger.info(
        "Prepared chat message created side effects for message %s in conversation %s: "
        "sender=%s recipients=%s created_statuses=%s existing_statuses=%s",
        message.id,
        message.group_id,
        message.sender_user_id,
        [hook["user_id"] for hook in notification_hooks],
        len(created_recipient_ids),
        len(existing_recipient_ids),
    )

    return {
        "status": "processed",
        "message_id": message.id,
        "conversation_id": message.group_id,
        "sender_id": message.sender_user_id,
        "recipient_ids": [hook["user_id"] for hook in notification_hooks],
        "created_status_count": len(created_recipient_ids),
        "existing_status_count": len(existing_recipient_ids),
        "notification_hooks_prepared": len(notification_hooks),
    }
