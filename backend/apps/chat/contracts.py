from collections import Counter

from .models import MessageStatus


def build_chat_message_payload(message):
    sender_name = ""
    if getattr(message, "sender_user", None) is not None:
        sender_name = message.sender_user.get_full_name().strip() or message.sender_user.email

    resource_links = list(message.resources.all())
    reaction_links = list(message.reactions.all())
    status_links = list(message.statuses.all())

    reactions = dict(Counter(reaction.emoji_string for reaction in reaction_links))
    read_by = sorted(
        status.user_id
        for status in status_links
        if status.status == MessageStatus.StatusChoices.READ
    )

    return {
        "id": message.id,
        "conversation_id": message.group_id,
        "sender_id": message.sender_user_id,
        "sender_name": sender_name,
        "body": message.message_text,
        "message_type": message.message_type,
        "created_at": message.sent_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "deleted_at": message.deleted_at.isoformat() if message.deleted_at else None,
        "is_deleted": message.deleted_at is not None,
        "is_edited": message.edited_at is not None,
        "resource_ids": [link.resource_id for link in resource_links],
        "resources": [
            {
                "id": link.resource_id,
                "resource_name": getattr(link.resource, "name", None),
            }
            for link in resource_links
        ],
        "reactions": reactions,
        "read_by": read_by,
    }
