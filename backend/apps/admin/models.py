from django.db import models
from django.conf import settings

class AdminUser(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    image = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    tracks = models.JSONField(null=True, blank=True)
    banned = models.BooleanField(default=False)
    ban_reason = models.TextField(null=True, blank=True)
    ban_expires = models.DateTimeField(null=True, blank=True)
    # References users_user table. Since django settings.AUTH_USER_MODEL is probably 'users.User' we use that
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_users')

    class Meta:
        db_table = 'admin_user'

class AdminSession(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    expires_at = models.DateTimeField()
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.TextField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name='sessions')
    impersonated_by = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'admin_session'
        indexes = [
            models.Index(fields=['user']),
        ]

class AdminAccount(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    account_id = models.TextField()
    provider_id = models.TextField()
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name='accounts')
    access_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    id_token = models.TextField(null=True, blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)
    password = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_account'
        indexes = [
            models.Index(fields=['user']),
        ]

class AdminVerification(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    identifier = models.TextField()
    value = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_verification'
        indexes = [
            models.Index(fields=['identifier']),
        ]

class MatchRun(models.Model):
    # SerialPrimaryKey is implicitly created by models.AutoField
    admin_user = models.ForeignKey(AdminUser, on_delete=models.PROTECT, related_name='match_runs')
    run_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField()

    class Meta:
        db_table = 'admin_match_run'
