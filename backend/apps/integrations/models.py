from django.db import models


class AdminUser(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    email_verified = models.BooleanField(blank=True, null=True)
    image = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_user"


class AdminAccount(models.Model):
    id = models.TextField(primary_key=True)
    account_id = models.TextField()
    provider_id = models.TextField()
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name="accounts")
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    access_token_expires_at = models.DateTimeField(blank=True, null=True)
    refresh_token_expires_at = models.DateTimeField(blank=True, null=True)
    scope = models.TextField(blank=True, null=True)
    password = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account"


class AdminSession(models.Model):
    id = models.TextField(primary_key=True)
    expires_at = models.DateTimeField()
    token = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.TextField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name="sessions")

    class Meta:
        db_table = "session"


class AdminMatchRun(models.Model):
    admin_user = models.ForeignKey(
        AdminUser,
        on_delete=models.PROTECT,
        related_name="admin_match_runs",
    )
    run_type = models.CharField(max_length=100)
    payload = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "admin_match_run"
