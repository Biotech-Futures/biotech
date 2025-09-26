from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets


class LoginToken(models.Model):
    """
    OTP tokens for passwordless email authentication
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_tokens'
    )
    token = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'login_tokens'
        verbose_name = "Login Token"
        verbose_name_plural = "Login Tokens"
        indexes = [
            models.Index(fields=['user', 'token']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Token {self.token} for {self.user.email} ({'used' if self.used else 'active'})"

    @property
    def is_expired(self):
        """Check if the token has expired"""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if the token is valid (not used and not expired)"""
        return not self.used and not self.is_expired

    def mark_as_used(self):
        """Mark the token as used"""
        self.used = True
        self.save(update_fields=['used'])

    @classmethod
    def generate_token(cls):
        """Generate a secure 6-digit numeric token"""
        return f"{secrets.randbelow(1000000):06d}"

    @classmethod
    def create_for_user(cls, user, expiry_minutes=10):
        """Create a new login token for a user"""
        token = cls.generate_token()
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )

    @classmethod
    def cleanup_expired(cls):
        """Remove expired tokens (should be run periodically)"""
        expired_tokens = cls.objects.filter(expires_at__lt=timezone.now())
        count = expired_tokens.count()
        expired_tokens.delete()
        return count

    @classmethod
    def verify_token_for_user(cls, user, token):
        """
        Verify a token for a specific user
        Returns the token object if valid, None otherwise
        Automatically marks valid tokens as used
        """
        try:
            login_token = cls.objects.get(
                user=user,
                token=token,
                used=False
            )

            if login_token.is_valid:
                login_token.mark_as_used()
                return login_token

        except cls.DoesNotExist:
            pass

        return None