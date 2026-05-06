from collections import Counter

from .models import MessageStatus
from .serializers import MessageSerializer


def build_reaction_summary(message):
    # Reaction rows are stored one-per-user-per-emoji. The frontend consumes the aggregate
    # map, so collapse them here for both REST responses and websocket broadcasts.
    counts = Counter(reaction.emoji_string for reaction in message.reactions.all())
    return {
        emoji: count
        for emoji, count in counts.items()
        if count > 0
    }


def build_read_by_summary(message):
    # Persisted messages expose the accumulated set of readers, while socket events broadcast
    # the latest reader separately. This helper produces the stored aggregate form.
    return sorted(
        status.user_id
        for status in message.statuses.all()
        if status.status == MessageStatus.StatusChoices.READ
    )


def build_chat_message_payload(message, *, request=None):
    # Centralize the frontend-facing contract so HTTP create/list handlers and websocket sends
    # stay aligned without each caller reassembling message fields by hand.
    context = {"request": request} if request is not None else {}
    return MessageSerializer(message, context=context).data
