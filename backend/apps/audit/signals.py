import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import AuditLog
from .services import log_audit_event


logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid="audit_successful_login")
def audit_successful_login(sender, request, user, **kwargs):
    try:
        log_audit_event(
            actor=user,
            entity_type="user",
            entity_id=user.pk,
            action=AuditLog.ActionChoices.LOGIN,
        )
    except Exception:
        # Audit persistence must not turn a valid login into an outage.
        logger.exception("Could not record successful login for user_id=%s", user.pk)
