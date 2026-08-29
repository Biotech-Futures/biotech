"""Confirmation email sent when a team submits.

Reports each component's status separately, which is what the client asked for:
a team can see at a glance that their poster arrived but their report did not.
"Absent" is their wording for not-yet-submitted and is not deadline-sensitive.
"""
from __future__ import annotations

import logging
import os
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from apps.common.role_names import ROLE_STUDENT
from apps.groups.models import GroupMembership
from apps.services.email_branding import brand_context
from apps.services.mailer import send_async

from .models import Submission, SubmissionQuestion
from .services import deadline_for_group


logger = logging.getLogger(__name__)

SUBMITTED = "Submitted"
ABSENT = "Absent"

# The shared helper in apps.services.email_branding attaches the *white* logo,
# because every other email puts it on a dark green header bar. This template
# has no bar — the masthead sits on a light card, where a white logo would be
# invisible — so the green variant is attached here under its own Content-ID.
# A local copy of a dozen lines is the cheaper trade than adding a variant
# parameter to a helper that five other apps depend on.
LOGO_CID = "btf-logo-green"
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "btf-logo-green.png")
_logo_bytes: bytes | None = None


def attach_green_logo(msg) -> None:
    """Embed the green logo inline. Best-effort: a missing asset falls back to alt text."""
    global _logo_bytes
    try:
        if _logo_bytes is None:
            with open(_LOGO_PATH, "rb") as fh:
                _logo_bytes = fh.read()
        img = MIMEImage(_logo_bytes, "png")
        img.add_header("Content-ID", f"<{LOGO_CID}>")
        img.add_header("Content-Disposition", "inline", filename="btf-logo.png")
        # Promotes the container to multipart/related so the cid: reference resolves.
        msg.mixed_subtype = "related"
        msg.attach(img)
    except OSError:
        logger.warning("submission_email.logo_missing path=%s", _LOGO_PATH)


def _format_deadline(closes_at) -> str:
    """"Friday, 18 September 2026", matching the client's copy.

    Built from parts rather than with a "%-d" directive: that strips the
    leading zero on Linux but is not a valid format on Windows, so a developer
    machine would raise where the server would not.
    """
    if not closes_at:
        return "the published deadline"
    local = timezone.localtime(closes_at)
    return f"{local:%A}, {local.day} {local:%B %Y}"


def _component(label: str, present: bool, detail: str = "") -> dict:
    return {
        "label": label,
        "submitted": present,
        "status": SUBMITTED if present else ABSENT,
        "detail": detail if present else "",
    }


def _saqs_present(submission: Submission) -> bool:
    """SAQs count as submitted once every required question is answered.

    Judged against the copy that was submitted, not the working draft — the
    email describes what is on record, not what someone is midway through
    editing.
    """
    answers = submission.submitted_answers or {}
    required = SubmissionQuestion.active().filter(is_required=True)
    if not required.exists():
        return bool(answers)
    return all(str(answers.get(q.key, "")).strip() for q in required)


def _file_detail(stored: dict | None) -> str:
    if not stored:
        return ""
    return stored.get("name") or ""


def build_components(submission: Submission) -> tuple[list[dict], list[dict]]:
    """Required and optional components, in the order the client's copy lists."""
    required = [
        _component("Poster", bool(submission.submitted_poster),
                   _file_detail(submission.submitted_poster)),
        _component("Short Answer Questions (SAQs)", _saqs_present(submission)),
    ]
    optional = [
        _component("Scientific Report", bool(submission.submitted_report),
                   _file_detail(submission.submitted_report)),
        _component(
            "Prototype",
            bool(submission.submitted_prototype) or bool(submission.submitted_prototype_url),
            _file_detail(submission.submitted_prototype)
            or submission.submitted_prototype_url,
        ),
    ]
    return required, optional


def recipients_for(group) -> list[str]:
    """Every student on the team.

    Mentors and supervisors are excluded deliberately: the client confirmed
    submissions are none of their business, so they should not receive a copy
    of a team's entry summary either.

    Accounts that are not active are excluded too, and that is deliberate
    rather than an oversight: an address nobody has validated is an address the
    programme has no business writing to, and a student who has not finished
    activating has not confirmed it is theirs.
    """
    memberships = (
        GroupMembership.objects.filter(group=group, left_at__isnull=True)
        .select_related("user")
    )
    emails = []
    for membership in memberships:
        user = membership.user
        if not user or not user.email or not user.is_active:
            continue
        # Membership role can be blank on older rows, so fall back to the
        # user's actual role rather than assuming.
        from apps.common.rbac import user_has_role

        if membership.membership_role == ROLE_STUDENT or user_has_role(user, ROLE_STUDENT):
            emails.append(user.email)
    return sorted(set(emails))


def send_individually(messages, *, kind: str) -> tuple[int, int]:
    """Send one message per recipient over a single connection.

    Everyone on a team receives the same email, addressed only to them. Two
    reasons for that over one message carrying the whole team in ``To``:

    * A team's students would otherwise see each other's addresses. These are
      school students, and one team's roster is not something the programme
      needs to hand out.
    * Mail servers reject a message per-message, not per-recipient. One
      mistyped address in a team of five could take the other four down with
      it, and nobody would receive anything.

    The connection is opened once and shared, so this costs one handshake for
    the team rather than one each. Each send is guarded separately: that is the
    whole point — a failure must cost one student their copy, not all of them.

    Returns ``(sent, failed)``.
    """
    if not messages:
        return 0, 0

    sent = failed = 0
    connection = get_connection()
    try:
        connection.open()
    except Exception:
        logger.error("submission_email.connection_failed kind=%s", kind)
        return 0, len(messages)

    try:
        for message in messages:
            message.connection = connection
            try:
                message.send()
            except Exception as exc:
                failed += 1
                # Not logger.exception: SMTPRecipientsRefused and friends carry
                # the recipient address in their args, which would land raw in
                # the log sink.
                logger.error(
                    "submission_email.recipient_failed kind=%s error=%s",
                    kind, type(exc).__name__,
                )
            else:
                sent += 1
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return sent, failed


class _Batch:
    """A set of messages that the mail pool can treat as one task.

    ``send_async`` hands whatever it is given to a worker and calls ``send()``
    on it, so wrapping the batch keeps a whole team's mail to a single slot on
    a pool that is shared with the login-code emails. Queueing five separate
    tasks for one submission would let a busy deadline evening push a student's
    sign-in code behind them.
    """

    def __init__(self, messages, kind: str):
        self.messages = messages
        self.kind = kind

    def send(self) -> int:
        sent, _ = send_individually(self.messages, kind=self.kind)
        return sent


def send_submission_confirmation(submission: Submission) -> int:
    """Email the team a summary of what was received. Returns recipient count.

    Never raises: a submission that succeeded must not be reported as failed
    because the confirmation could not be sent.
    """
    try:
        group = submission.group
        to = recipients_for(group)
        if not to:
            logger.warning("submission_email.no_recipients group=%s", group.id)
            return 0

        required, optional = build_components(submission)
        deadline = deadline_for_group(group.id)

        context = {
            **brand_context(),
            "LOGO_URL": f"cid:{LOGO_CID}",
            "GROUP_NAME": group.group_name,
            "YEAR": timezone.now().year,
            "REQUIRED_COMPONENTS": required,
            "OPTIONAL_COMPONENTS": optional,
            "INCOMPLETE": any(not item["submitted"] for item in required),
            "DEADLINE": _format_deadline(deadline.closes_at),
            "SUBMITTED_BY": submission.submitted_by,
            # Hash routing, so the path lives after the "#". Blank base means
            # no button rather than a link to nowhere — the template checks.
            "SUBMISSION_URL": (
                f"{settings.FRONTEND_BASE_URL}/#/submission/{group.id}"
                if getattr(settings, "FRONTEND_BASE_URL", "")
                else ""
            ),
        }

        html = render_to_string("emails/submission_confirmation.html", context)
        # Rendered from its own template rather than stripped out of the HTML:
        # strip_tags keeps the text between tags, so the base template's <style>
        # block arrived as visible CSS at the top of the message.
        text = render_to_string("emails/submission_confirmation.txt", context)

        # Rendered once and reused, so every student on the team is looking at
        # the same email — only the address it is sent to differs.
        subject = f"{settings.BRAND_NAME}: Submission received for {group.group_name}"
        messages = []
        for address in to:
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[address],
            )
            message.attach_alternative(html, "text/html")
            attach_green_logo(message)
            messages.append(message)

        # Rendered here, sent off-thread: the worker does no ORM work, so it
        # can never race the transaction that created this submission.
        send_async(_Batch(messages, "submission_confirmation"),
                   kind="submission_confirmation")
        return len(to)
    except Exception:
        logger.exception("submission_email.failed group=%s", getattr(submission, "group_id", None))
        return 0
