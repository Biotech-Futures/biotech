from .models import AuditLog


def log_audit_event(*, actor=None, entity_type, entity_id, action, before_state=None, after_state=None):
    return AuditLog.objects.create(
        actor_user=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
    )

