import hashlib
import logging
import re
import threading
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.db import IntegrityError, connections, models, transaction
from django.conf import settings
from django.utils import timezone

from apps.chat.models import MessageScreening, MessageScreeningStatus, Messages, MessageType

logger = logging.getLogger(__name__)


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


@dataclass(frozen=True)
class ScreeningResult:
    status: str
    risk_score: Decimal
    category: str = ""
    reason: str = ""
    layer: str = "llm"
    provider: str = "omni-moderation-latest"
    categories: dict[str, bool] | None = None
    category_scores: dict[str, float] | None = None

    @property
    def flagged(self) -> bool:
        return self.status == MessageScreeningStatus.FLAGGED


def message_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def should_screen_message(message: Messages) -> bool:
    if (
        message.deleted_at is not None
        or message.message_type == MessageType.SYSTEM
        or not (message.message_text or "").strip()
    ):
        return False
    text_hash = message_text_hash(message.message_text)
    existing_status = MessageScreening.objects.filter(
        message=message,
        text_hash=text_hash,
    ).values_list("status", flat=True).first()
    return existing_status is None or existing_status == MessageScreeningStatus.FAILED


def _redact_personal_data(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL_ADDRESS]", text or "")
    return _PHONE_RE.sub("[PHONE_NUMBER]", text)


def _minimal_ai_input(screening: MessageScreening) -> str:
    """Send only the current message, with obvious contact data redacted."""
    max_chars = max(1, getattr(settings, "AI_SCREENING_MAX_INPUT_CHARS", 4000))
    return _redact_personal_data(screening.message_snapshot)[:max_chars]


def run_external_ai_moderation(screening: MessageScreening) -> ScreeningResult:
    """Classify one queued message with OpenAI's Moderations endpoint."""
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = getattr(
        settings, "AI_SCREENING_OPENAI_MODEL", "omni-moderation-latest"
    )
    response = requests.post(
        getattr(
            settings,
            "AI_SCREENING_OPENAI_URL",
            "https://api.openai.com/v1/moderations",
        ),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "input": _minimal_ai_input(screening)},
        timeout=getattr(settings, "AI_SCREENING_OPENAI_TIMEOUT_SECONDS", 15),
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") or []
    if not results or not isinstance(results[0], dict):
        raise ValueError("OpenAI moderation response did not contain a result")

    result = results[0]
    categories = {
        str(name): bool(value)
        for name, value in (result.get("categories") or {}).items()
    }
    raw_scores = result.get("category_scores") or {}
    scores = {
        name: Decimal(str(score))
        for name, score in raw_scores.items()
        if isinstance(score, (int, float))
    }
    flagged_categories = [
        name for name, is_flagged in categories.items() if is_flagged is True
    ]
    flagged = bool(result.get("flagged"))
    relevant_scores = (
        [scores[name] for name in flagged_categories if name in scores]
        if flagged
        else list(scores.values())
    )
    risk_score = max(relevant_scores, default=Decimal("0"))
    category = ""
    if flagged_categories:
        category = max(flagged_categories, key=lambda name: scores.get(name, Decimal("0")))
    elif flagged and scores:
        category = max(scores, key=scores.get)

    return ScreeningResult(
        status=(
            MessageScreeningStatus.FLAGGED
            if flagged
            else MessageScreeningStatus.SAFE
        ),
        risk_score=risk_score.quantize(Decimal("0.0001")),
        category=category,
        reason=(
            f"OpenAI moderation flagged: {', '.join(flagged_categories)}"
            if flagged_categories
            else "OpenAI moderation flagged this message"
            if flagged
            else "OpenAI moderation did not flag this message"
        ),
        layer="llm",
        provider=str(payload.get("model") or model)[:80],
        categories=categories,
        category_scores={name: float(score) for name, score in scores.items()},
    )


def create_ticket_for_flagged_message(
    screening: MessageScreening,
    verdict: ScreeningResult,
):
    """Hand a flagged verdict to the ticket system's frozen interface."""
    # Import locally so the chat models can be loaded without pulling the
    # ticket service (and its audit dependencies) into Django's app startup.
    from apps.tickets.services.handoff import create_ticket_from_screening

    return create_ticket_from_screening(
        screening.message,
        verdict,
        screening.message_snapshot,
    )


def screen_message(message: Messages) -> MessageScreening:
    """Create the durable queue record for one message version."""
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
                    "status": MessageScreeningStatus.SUSPICIOUS,
                    "message_snapshot": text,
                    "provider": "openai",
                },
            )
    except IntegrityError:
        return MessageScreening.objects.get(message=message, text_hash=text_hash)

    if not created and screening.status == MessageScreeningStatus.FAILED:
        screening.status = MessageScreeningStatus.SUSPICIOUS
        screening.save(update_fields=["status", "updated_at"])
    return screening


def screen_suspicious_message(screening_id: int) -> MessageScreening | None:
    """Moderate one queued record and create exactly one ticket if flagged."""
    try:
        screening = (
            MessageScreening.objects
            .select_related("message", "message__group", "message__sender_user")
            .get(pk=screening_id)
        )
        if screening.status != MessageScreeningStatus.SUSPICIOUS:
            return screening

        MessageScreening.objects.filter(
            pk=screening_id,
            status=MessageScreeningStatus.SUSPICIOUS,
        ).update(
            attempt_count=models.F("attempt_count") + 1,
            last_attempt_at=timezone.now(),
        )
        verdict = run_external_ai_moderation(screening)

        with transaction.atomic():
            screening = (
                MessageScreening.objects
                .select_for_update()
                .select_related("message", "message__group", "message__sender_user")
                .get(pk=screening_id)
            )
            if screening.status != MessageScreeningStatus.SUSPICIOUS:
                return screening
            screening.status = verdict.status
            screening.risk_score = verdict.risk_score
            screening.category = verdict.category
            screening.reason = verdict.reason
            screening.provider = verdict.provider
            screening.categories = verdict.categories or {}
            screening.category_scores = verdict.category_scores or {}
            screening.error_message = ""
            screening.screened_at = timezone.now()
            screening.save(
                update_fields=[
                    "status",
                    "risk_score",
                    "category",
                    "reason",
                    "provider",
                    "categories",
                    "category_scores",
                    "error_message",
                    "screened_at",
                    "updated_at",
                ]
            )

            if verdict.flagged:
                ticket = create_ticket_for_flagged_message(screening, verdict)
                screening.ticket = ticket
                screening.save(update_fields=["ticket", "updated_at"])
            return screening
    except MessageScreening.DoesNotExist:
        return None
    except Exception as exc:
        MessageScreening.objects.filter(
            pk=screening_id,
            status=MessageScreeningStatus.SUSPICIOUS,
        ).update(error_message=str(exc), updated_at=timezone.now())
        logger.exception("message_screening.ai_failed screening_id=%s", screening_id)
        return None


def process_suspicious_messages(limit: int | None = None) -> dict[str, int]:
    """Process the oldest suspicious records; safe for overlapping workers."""
    limit = limit or getattr(settings, "AI_SCREENING_BATCH_LIMIT", 100)
    limit = max(1, min(int(limit), 1000))
    ids = list(
        MessageScreening.objects.filter(
            status=MessageScreeningStatus.SUSPICIOUS,
            message__deleted_at__isnull=True,
        )
        .order_by("created_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    counts = {"considered": len(ids), "safe": 0, "flagged": 0, "failed": 0}
    for screening_id in ids:
        result = screen_suspicious_message(screening_id)
        if result is None:
            counts["failed"] += 1
        elif result.status == MessageScreeningStatus.FLAGGED:
            counts["flagged"] += 1
        elif result.status == MessageScreeningStatus.SAFE:
            counts["safe"] += 1
    return counts


_ai_dispatch_lock = threading.Lock()


def _run_ai_screening_in_thread() -> None:
    try:
        counts = process_suspicious_messages()
        logger.info("message_screening.ai_completed %s", counts)
    except Exception:
        logger.exception("message_screening.ai_worker_crashed")
    finally:
        connections.close_all()
        _ai_dispatch_lock.release()


def dispatch_suspicious_message_screening() -> str:
    """Start one batch without allowing overlapping runs in this process."""
    if not _ai_dispatch_lock.acquire(blocking=False):
        return "already_running"
    if getattr(settings, "AI_SCREENING_DISPATCH_SYNC", False):
        try:
            process_suspicious_messages()
            return "completed"
        finally:
            _ai_dispatch_lock.release()

    worker = threading.Thread(
        target=_run_ai_screening_in_thread,
        name="ai-message-screening",
        daemon=True,
    )
    worker.start()
    return "started"


def dispatch_message_screening(message: Messages) -> MessageScreening | None:
    if not should_screen_message(message):
        return None
    return screen_message(message)


def schedule_message_screening(message: Messages) -> None:
    """Queue after commit, process immediately when configured, and retain cron fallback."""
    message_id = message.pk

    def _enqueue() -> None:
        try:
            current = Messages.objects.get(pk=message_id)
        except Messages.DoesNotExist:
            return
        screening = dispatch_message_screening(current)
        if screening is not None and getattr(settings, "OPENAI_API_KEY", ""):
            dispatch_suspicious_message_screening()

    transaction.on_commit(_enqueue)
