from django.db import models
from django.utils import timezone


class AdminUser(models.Model):
    """
    External admin auth system user (NextAuth / BetterAuth / Lucia style).
    The id is a TEXT primary key — the caller must supply it (e.g. UUID string)
    before calling .save() / .objects.create().
    """
    id = models.TextField(primary_key=True)
    name = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    email_verified = models.BooleanField(null=True, blank=True)
    image = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_user"
        verbose_name = "Admin User"
        verbose_name_plural = "Admin Users"
        indexes = [
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.email or self.id


class Account(models.Model):
    """
    OAuth / credential account linked to an AdminUser.
    Maps to the 'account' table (BetterAuth / NextAuth convention).
    """
    id = models.TextField(primary_key=True)
    account_id = models.TextField()
    provider_id = models.TextField()
    user = models.ForeignKey(
        AdminUser,
        on_delete=models.CASCADE,
        related_name="accounts",
        db_column="user_id",
    )
    access_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)
    password = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account"
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["provider_id", "account_id"]),
        ]

    def __str__(self):
        return f"{self.provider_id}:{self.account_id}"


class AdminSession(models.Model):
    """
    Admin auth session token (BetterAuth / NextAuth / Lucia convention).
    Table name is 'session' to match the DDL exactly.
    """
    id = models.TextField(primary_key=True)
    expires_at = models.DateTimeField()
    token = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.TextField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        AdminUser,
        on_delete=models.CASCADE,
        related_name="admin_sessions",
        db_column="user_id",
    )

    class Meta:
        db_table = "session"
        verbose_name = "Admin Session"
        verbose_name_plural = "Admin Sessions"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Session {self.id[:8]}… (user={self.user_id})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class AdminMatchRun(models.Model):
    """
    Admin-panel-initiated match run.
    Separate from the algorithm-level MatchRun in apps.matching_runtime
    to preserve that table's algorithm-specific columns.
    """
    admin_user = models.ForeignKey(
        AdminUser,
        on_delete=models.RESTRICT,
        related_name="match_runs",
        db_column="admin_user_id",
    )
    run_type = models.CharField(max_length=100)
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    result = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "admin_match_run"
        verbose_name = "Admin Match Run"
        verbose_name_plural = "Admin Match Runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin_user"]),
            models.Index(fields=["run_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.run_type} at {self.created_at:%Y-%m-%d %H:%M:%S}"
