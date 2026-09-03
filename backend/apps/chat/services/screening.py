import hashlib
import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.conf import settings
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages
from apps.common.text import DEFAULT_REPLACEMENT

logger = logging.getLogger(__name__)


SCREENING_PROVIDER = "local_stub"

_FLAGGED_KEYWORDS = {
    "hate": ("harassment", Decimal("0.9000")),
    "threat": ("threat", Decimal("0.9500")),
    "kill": ("threat", Decimal("0.9500")),
}

MASKED_PROFANITY_CATEGORY = "masked_profanity"
MASKED_PROFANITY_SCORE = Decimal("0.8000")


@dataclass(frozen=True)
class ScreeningResult:
    status: str
    risk_score: Decimal
    category: str = ""
    reason: str = ""


def message_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def should_screen_message(message: Messages) -> bool:
    if message.deleted_at is not None:
        return False
    text_hash = message_text_hash(message.message_text)
    return not MessageScreening.objects.filter(
        message=message,
        text_hash=text_hash,
    ).exists()


def sanitizer_replacement_token() -> str:
    return getattr(settings, "CHAT_SANITIZER_REPLACEMENT", DEFAULT_REPLACEMENT)


def run_local_screening_stub(text: str) -> ScreeningResult:
    normalized = (text or "").lower()
    replacement = sanitizer_replacement_token()
    if replacement and replacement in (text or ""):
        return ScreeningResult(
            status=MessageScreeningStatus.FLAGGED,
            risk_score=MASKED_PROFANITY_SCORE,
            category=MASKED_PROFANITY_CATEGORY,
            reason=f"Matched sanitizer replacement token: {replacement}",
        )

    for keyword, (category, score) in _FLAGGED_KEYWORDS.items():
        if keyword in normalized:
            return ScreeningResult(
                status=MessageScreeningStatus.FLAGGED,
                risk_score=score,
                category=category,
                reason=f"Matched local screening keyword: {keyword}",
            )
    return ScreeningResult(
        status=MessageScreeningStatus.SAFE,
        risk_score=Decimal("0.0000"),
    )


def create_ticket_for_flagged_message(screening: MessageScreening):
    """Hook for the enquiry/ticketing system.

    The ticketing teammate can replace this no-op with an import or service call
    once that system's model/API contract is settled.
    """
    logger.info(
        "message_screening.flagged ticket hook pending screening_id=%s message_id=%s",
        screening.id,
        screening.message_id,
    )
    return None


def screen_message(message: Messages) -> MessageScreening:
    text = message.message_text or ""
    text_hash = message_text_hash(text)

    try:
        with transaction.atomic():
            screening, created = MessageScreening.objects.get_or_create(
                message=message,
                text_hash=text_hash,
                defaults={
                    "group_id": message.group_id,
                    "sender_user_id": message.sender_user_id,
                    "status": MessageScreeningStatus.PENDING,
                    "message_snapshot": text,
                    "provider": SCREENING_PROVIDER,
                },
            )
    except IntegrityError:
        return MessageScreening.objects.get(message=message, text_hash=text_hash)

    if not created and screening.status != MessageScreeningStatus.PENDING:
        return screening

    try:
        result = run_local_screening_stub(text)
        screening.status = result.status
        screening.risk_score = result.risk_score
        screening.category = result.category
        screening.reason = result.reason
        screening.error_message = ""
        screening.screened_at = timezone.now()
        screening.save(
            update_fields=[
                "status",
                "risk_score",
                "category",
                "reason",
                "error_message",
                "screened_at",
                "updated_at",
            ]
        )
    except Exception as exc:
        screening.status = MessageScreeningStatus.FAILED
        screening.error_message = str(exc)
        screening.screened_at = timezone.now()
        screening.save(
            update_fields=[
                "status",
                "error_message",
                "screened_at",
                "updated_at",
            ]
        )
        logger.exception(
            "message_screening.failed screening_id=%s message_id=%s",
            screening.id,
            message.id,
        )
        return screening

    if screening.status == MessageScreeningStatus.FLAGGED:
        create_ticket_for_flagged_message(screening)

    return screening


def dispatch_message_screening(message: Messages) -> MessageScreening | None:
    if not should_screen_message(message):
        return None
    return screen_message(message)
