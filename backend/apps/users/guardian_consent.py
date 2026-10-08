"""Guardian consent on the platform: the emailed link, the signed form and
withdrawals.

An admin sends a request; the guardian follows the link, reads the form,
answers the media-consent question and signs. Signing records a
``GuardianConsent`` and marks the student as consented, the same flags the old
Qualtrics webhook set, so everything that checks consent keeps working.
"""
import base64
import binascii
import hashlib
import io
import logging
import secrets
from datetime import timedelta
from typing import NamedTuple, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.audit.services import log_audit_event
from apps.common.storage import get_consent_storage

from .consent_form import CURRENT_VERSION, render_consent_form
from .consent_pdf import render_consent_pdf
from .models import GuardianConsent, GuardianConsentRequest, StudentProfile

logger = logging.getLogger(__name__)

LINK_LIFETIME = timedelta(days=14)
# The drawn signature, as a PNG data URL from the page's canvas.
SIGNATURE_PREFIX = "data:image/png;base64,"
MAX_SIGNATURE_BYTES = 300 * 1024
MAX_SIGNATURE_SIDE = 2000


class ConsentLinkError(Exception):
    """A consent link that can't be used, with a code the page can act on."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Guardian(NamedTuple):
    first_name: str
    last_name: str
    email: str
    pending: bool


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def student_name(profile: StudentProfile) -> str:
    user = profile.user
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def is_placeholder_name(first: str, last: str, profile: StudentProfile) -> bool:
    """A student created without a guardian has their own name copied into the
    guardian fields; that isn't the guardian's name."""
    guardian = f"{first or ''} {last or ''}".strip().lower()
    return not guardian or guardian == student_name(profile).lower()


def guardian_to_ask(profile: StudentProfile) -> Optional[Guardian]:
    """Whose consent is still needed: a requested guardian change first, else
    the guardian on file while consent is missing. None when nobody is."""
    if profile.has_pending_guardian:
        return Guardian(
            profile.pending_pg_first_name, profile.pending_pg_last_name,
            (profile.pending_pg_email or "").strip().lower(), True,
        )
    if profile.has_join_permission:
        return None
    return Guardian(
        profile.pg_first_name, profile.pg_last_name, (profile.pg_email or "").strip().lower(), False,
    )


def consent_link(token: str) -> str:
    return f"{settings.FRONTEND_BASE_URL}/#/consent/{token}"


def issue_request(profile: StudentProfile, guardian: Guardian, sent_by=None) -> tuple:
    """A new consent link for ``guardian``. Earlier links for the student stop
    working, so only the newest email's link can be used. Returns the request
    and the raw token, which exists only in the emailed link."""
    now = timezone.now()
    GuardianConsentRequest.objects.filter(
        student=profile, used_at__isnull=True, revoked_at__isnull=True,
    ).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    request = GuardianConsentRequest.objects.create(
        student=profile,
        token_hash=_hash(token),
        guardian_first_name=guardian.first_name,
        guardian_last_name=guardian.last_name,
        guardian_email=guardian.email,
        for_pending_guardian=guardian.pending,
        sent_by=sent_by,
        expires_at=now + LINK_LIFETIME,
    )
    return request, token


def open_request(token: str, *, for_update: bool = False) -> GuardianConsentRequest:
    """The request behind a consent link, if the link can still be used."""
    queryset = GuardianConsentRequest.objects.select_related("student__user")
    if for_update:
        queryset = queryset.select_for_update()
    request = queryset.filter(token_hash=_hash(token or "")).first()
    if request is None:
        raise ConsentLinkError("invalid", "This consent link isn't valid. Check you opened the whole link from the email.")
    if request.used_at:
        raise ConsentLinkError("used", "This consent form has already been signed. Thank you.")
    if request.revoked_at:
        raise ConsentLinkError("replaced", "A newer consent link has been sent. Please use the link in the most recent email.")
    if request.expires_at <= timezone.now():
        raise ConsentLinkError("expired", "This consent link has expired. Contact us and we'll send a new one.")
    current = guardian_to_ask(request.student)
    if current is None or current.email != request.guardian_email or current.pending != request.for_pending_guardian:
        # The student's guardian, or their consent, changed after this was sent.
        raise ConsentLinkError("out_of_date", "This consent link is out of date. Contact us and we'll send a new one.")
    return request


def form_for(request: GuardianConsentRequest) -> dict:
    """What the consent page shows for a valid link."""
    profile = request.student
    first = request.guardian_first_name
    if is_placeholder_name(first, request.guardian_last_name, profile):
        first = ""
    return {
        "studentName": student_name(profile),
        "guardianFirstName": first,
        "guardianLastName": "" if not first else request.guardian_last_name,
        "expiresAt": request.expires_at.isoformat(),
        "supportEmail": settings.SUPPORT_EMAIL,
        "form": render_consent_form(student_name(profile)),
    }


def decode_signature(data_url: str) -> bytes:
    """The PNG bytes of a drawn signature. Raises ValueError for anything that
    isn't a reasonably sized PNG with something drawn on it."""
    if not isinstance(data_url, str) or not data_url.startswith(SIGNATURE_PREFIX):
        raise ValueError("Please sign in the signature box.")
    encoded = data_url[len(SIGNATURE_PREFIX):]
    if len(encoded) > MAX_SIGNATURE_BYTES * 4 // 3 + 4:
        raise ValueError("The signature is too large. Please clear it and sign again.")
    try:
        png = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The signature couldn't be read. Please clear it and sign again.")
    try:
        image = Image.open(io.BytesIO(png))
        image.verify()
        image = Image.open(io.BytesIO(png))
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("The signature couldn't be read. Please clear it and sign again.")
    if image.format != "PNG" or max(image.size) > MAX_SIGNATURE_SIDE:
        raise ValueError("The signature couldn't be read. Please clear it and sign again.")
    # A blank canvas is fully transparent: nothing to bound.
    if image.convert("RGBA").getchannel("A").getbbox() is None:
        raise ValueError("Please sign in the signature box.")
    return png


def sign(token: str, *, full_name: str, media_consent: bool, signature: str,
         version: str, ip: Optional[str], user_agent: str) -> GuardianConsent:
    """Record the guardian's signed consent. Raises ConsentLinkError for a link
    that can't be used and ValueError for a form that isn't complete."""
    full_name = " ".join((full_name or "").split())
    if not full_name:
        raise ValueError("Please enter your full name.")
    if version != CURRENT_VERSION:
        raise ValueError("The consent form has been updated. Please reload the page and read it again.")
    png = decode_signature(signature)

    with transaction.atomic():
        request = open_request(token, for_update=True)
        profile = StudentProfile.objects.select_for_update().get(pk=request.student_id)
        now = timezone.now()

        consent = GuardianConsent.objects.create(
            student=profile,
            request=request,
            guardian_full_name=full_name[:255],
            guardian_email=request.guardian_email,
            media_consent=media_consent,
            signature_png=png,
            consent_version=version,
            signed_ip=ip,
            signed_user_agent=(user_agent or "")[:512],
        )
        request.used_at = now
        request.save(update_fields=["used_at"])

        if request.for_pending_guardian:
            profile.promote_pending_guardian()
        profile.parent_guardian_flag = True
        profile.has_join_permission = True
        profile.joinperm_responseID = consent.reference
        profile.joinperm_granted_at = now
        profile.media_consent = media_consent
        profile.save()

        log_audit_event(
            actor=None,
            entity_type="user",
            entity_id=profile.user_id,
            action="guardian_consent_signed",
            after_state={
                "consentId": consent.pk,
                "guardianEmail": consent.guardian_email,
                "mediaConsent": media_consent,
                "consentVersion": version,
            },
        )

    store_record_pdf(consent, render_consent_pdf(consent))
    return consent


def record_pdf_filename(consent: GuardianConsent) -> str:
    # The reference alone: plain ASCII whatever the student's name is written in.
    return f"{consent.reference}-consent-record.pdf"


def store_record_pdf(consent: GuardianConsent, pdf: bytes) -> bool:
    """Keep the signed record in the guardian-consent-forms container. A failure is logged,
    not raised: the consent is already recorded and the PDF can be rebuilt
    from it whenever it's next asked for."""
    try:
        key = get_consent_storage().save(f"{consent.student_id}/{consent.reference}.pdf", ContentFile(pdf))
    except Exception as exc:
        logger.error("guardian_consent.record_store_failed consent=%s error=%s", consent.pk, type(exc).__name__)
        return False
    consent.record_pdf_key = key
    consent.save(update_fields=["record_pdf_key"])
    return True


def record_pdf_bytes(consent: GuardianConsent) -> bytes:
    """The signed record's PDF: the stored copy, or a rebuilt one (stored for
    next time) if it was never stored or has gone missing."""
    storage = get_consent_storage()
    if consent.record_pdf_key:
        try:
            with storage.open(consent.record_pdf_key) as stored:
                return stored.read()
        except Exception as exc:
            logger.warning(
                "guardian_consent.record_open_failed consent=%s error=%s", consent.pk, type(exc).__name__,
            )
    pdf = render_consent_pdf(consent)
    store_record_pdf(consent, pdf)
    return pdf


def withdraw(profile: StudentProfile, *, media_only: bool, initiated_by=None) -> None:
    """Record a guardian's withdrawal, which they ask for by contacting support.
    Withdrawing media consent keeps participation consent; withdrawing consent
    ends both, and the student needs a new consent to take part again."""
    with transaction.atomic():
        profile = StudentProfile.objects.select_for_update().get(pk=profile.pk)
        now = timezone.now()
        before = {"joinPermissionReceived": profile.has_join_permission, "mediaConsent": profile.media_consent}
        latest = profile.consents.filter(withdrawn_at__isnull=True).order_by("-signed_at").first()

        if media_only:
            profile.media_consent = False
            profile.save(update_fields=["media_consent"])
            if latest and latest.media_consent and latest.media_withdrawn_at is None:
                latest.media_withdrawn_at = now
                latest.save(update_fields=["media_withdrawn_at"])
        else:
            profile.has_join_permission = False
            profile.joinperm_responseID = None
            profile.joinperm_granted_at = None
            profile.media_consent = None
            profile.save(update_fields=[
                "has_join_permission", "joinperm_responseID", "joinperm_granted_at", "media_consent",
            ])
            if latest:
                latest.withdrawn_at = now
                latest.save(update_fields=["withdrawn_at"])

        log_audit_event(
            actor=initiated_by,
            entity_type="user",
            entity_id=profile.user_id,
            action="guardian_media_consent_withdrawn" if media_only else "guardian_consent_withdrawn",
            before_state=before,
            after_state={"joinPermissionReceived": profile.has_join_permission, "mediaConsent": profile.media_consent},
        )
