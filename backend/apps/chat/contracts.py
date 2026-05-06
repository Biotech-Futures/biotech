from collections import Counter

from .models import MessageStatus
from .serializers import MessageSerializer


def build_reaction_summary(message):
    counts = Counter(reaction.emoji_string for reaction in message.reactions.all())
    return {
        emoji: count
        for emoji, count in counts.items()
        if count > 0
    }


def build_read_by_summary(message):
    return sorted(
        status.user_id
        for status in message.statuses.all()
        if status.status == MessageStatus.StatusChoices.READ
    )


def build_chat_message_payload(message, *, request=None):
    context = {"request": request} if request is not None else {}
    return MessageSerializer(message, context=context).data
