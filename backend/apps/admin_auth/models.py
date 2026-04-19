# ADMIN AUTH MODELS
import uuid

from django.db import models
from django.utils import timezone


def default_admin_id():
    # Generates a UUID hex string as the default TEXT primary key,
    # consistent with external auth systems (BetterAuth / NextAuth / Lucia).
    return uuid.uuid4().hex


class AdminUser(models.Model):
    id = models.TextField(primary_key=True, default=default_admin_id)  # TEXT PK to match external auth system convention
    name = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    email_verified = models.BooleanField(null=True, blank=True)
    image = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "admin_user"
        verbose_name = "Admin User"
        verbose_name_plural = "Admin Users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),  # login lookup
        ]

    def __str__(self):
        return self.email or self.id


class Account(models.Model):
    id = models.TextField(primary_key=True, default=default_admin_id)  # TEXT PK to match external auth system convention
    account_id = models.TextField()
    provider_id = models.TextField()
    user = models.ForeignKey(
        AdminUser,
        on_delete=models.CASCADE,  # remove accounts when the admin user is deleted
        related_name="accounts",
        db_column="user_id",  # explicit column name to match DDL exactly
    )
    access_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)
    password = models.TextField(null=True, blank=True)  # used for credential-based providers only
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "account"
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        indexes = [
            # lookup by user
            models.Index(fields=["user"]),
            # lookup by provider + account (e.g. OAuth callback)
            models.Index(fields=["provider_id", "account_id"]),
        ]

    def __str__(self):
        return f"{self.provider_id}:{self.account_id}"


class AdminSession(models.Model):
    # db_table is 'session' to match the DDL — distinct from user_session used by the main platform
    id = models.TextField(primary_key=True, default=default_admin_id)  # TEXT PK to match external auth system convention
    expires_at = models.DateTimeField()
    token = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    ip_address = models.TextField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        AdminUser,
        on_delete=models.CASCADE,  # remove sessions when the admin user is deleted
        related_name="admin_sessions",
        db_column="user_id",  # explicit column name to match DDL exactly
    )

    class Meta:
        db_table = "session"
        verbose_name = "Admin Session"
        verbose_name_plural = "Admin Sessions"
        ordering = ["-created_at"]
        indexes = [
            # lookup active sessions by user
            models.Index(fields=["user"]),
            # token-based session resolution
            models.Index(fields=["token"]),
            # expiry check on every request
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} [{self.id[:8]}]"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class AdminMatchRun(models.Model):
    admin_user = models.ForeignKey(
        AdminUser,
        on_delete=models.RESTRICT,  # prevent deleting an admin user who has initiated match runs
        related_name="match_runs",
        db_column="admin_user_id",  # explicit column name to match DDL exactly
    )
    run_type = models.CharField(max_length=100)
    payload = models.JSONField(null=True, blank=True)  # input parameters / config for the run
    created_at = models.DateTimeField(default=timezone.now)
    result = models.JSONField(null=True, blank=True)  # output / summary written back after the run completes

    class Meta:
        db_table = "admin_match_run"
        verbose_name = "Admin Match Run"
        verbose_name_plural = "Admin Match Runs"
        ordering = ["-created_at"]
        indexes = [
            # filter runs by who triggered them
            models.Index(fields=["admin_user"]),
            # filter by run type
            models.Index(fields=["run_type"]),
            # chronological listing
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.run_type} at {self.created_at:%Y-%m-%d %H:%M:%S}"
