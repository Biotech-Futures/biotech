from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    class ActionChoices(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        EXPORT = "export", "Export"
        IMPORT = "import", "Import"

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    entity_type = models.CharField(max_length=100)
    entity_id = models.BigIntegerField()
    action = models.CharField(max_length=100, choices=ActionChoices.choices)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor_user"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"

