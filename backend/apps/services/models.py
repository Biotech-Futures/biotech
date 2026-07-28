from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets

# Single source of truth — the login email quotes this value back to the user.
LOGIN_OTP_EXPIRY_MINUTES = 10

# A resend refreshes the window, so without a hard cap a 6-digit secret could be
# kept alive indefinitely by an attacker who can trigger resends.
LOGIN_OTP_MAX_LIFETIME_MINUTES = 30

# Below this much life left, reuse is worse than a new code: the email promises
# LOGIN_OTP_EXPIRY_MINUTES, and the 60s send cooldown would strand the user.
LOGIN_OTP_MIN_REUSABLE_SECONDS = 120


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
    def create_for_user(cls, user, expiry_minutes=LOGIN_OTP_EXPIRY_MINUTES):
        """Create a new login token for a user and invalidate old ones."""
        # Clean Code: Enforce single active token per user
        cls.objects.filter(user=user, used=False).update(used=True)

        token = cls.generate_token()
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )

    @classmethod
    def get_or_create_active(
        cls,
        user,
        expiry_minutes=LOGIN_OTP_EXPIRY_MINUTES,
        max_lifetime_minutes=LOGIN_OTP_MAX_LIFETIME_MINUTES,
    ):
        """Return the user's live token, refreshing its window, or mint a new one.

        Resending must not burn the code already sitting in the user's inbox —
        slow mail means they often open an older email than the one we just sent.
        """
        with transaction.atomic():
            # Lock the user row, not the token queryset: SELECT FOR UPDATE over an
            # empty result set locks nothing, so two concurrent sends would both
            # mint a token and the second would invalidate the first.
            locked_user = user.__class__.objects.select_for_update().get(pk=user.pk)

            now = timezone.now()
            live = (
                cls.objects
                .filter(user=locked_user, used=False, expires_at__gt=now)
                .order_by('-created_at')
                .first()
            )

            if live is not None:
                # Capped at the hard deadline, and never shortened: past the cap
                # the token stays usable for its remaining life, just not extendable.
                hard_deadline = live.created_at + timedelta(minutes=max_lifetime_minutes)
                target = max(
                    live.expires_at,
                    min(now + timedelta(minutes=expiry_minutes), hard_deadline),
                )

                # Don't re-send a code that's about to die on arrival — past the
                # cap `target` can't move, so reuse would email a near-dead code.
                if (target - now).total_seconds() < LOGIN_OTP_MIN_REUSABLE_SECONDS:
                    return cls.create_for_user(locked_user, expiry_minutes=expiry_minutes)

                # Guarded on used=False because verify doesn't take the user lock:
                # a zero rowcount means it was consumed between the read and here,
                # so mint a new one rather than emailing a dead code.
                if cls.objects.filter(pk=live.pk, used=False).update(expires_at=target):
                    live.expires_at = target
                    return live

            return cls.create_for_user(locked_user, expiry_minutes=expiry_minutes)

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
        # .first() rather than .get(): a create race can leave two unused rows with
        # the same digits, and MultipleObjectsReturned here would 500 the login path.
        login_token = (
            cls.objects
            .filter(user=user, token=token, used=False)
            .order_by('-created_at')
            .first()
        )

        if login_token is not None and login_token.is_valid:
            login_token.mark_as_used()
            return login_token

        return None


class PasswordResetToken(models.Model):
    """High-entropy single-use token issued via email for self-service password reset."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    # secrets.token_urlsafe(32) -> 43-char base64url string; 64 leaves room
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_user_agent = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
        indexes = [
            models.Index(fields=['user', 'used']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"PasswordReset({self.user.email}, {'used' if self.used else 'active'})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired

    def mark_as_used(self):
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_user(cls, user, *, expiry_minutes=30, ip=None, user_agent=""):
        """Issue a new token; invalidate any prior unused token for the same user."""
        # one active token per user
        cls.objects.filter(user=user, used=False).update(used=True, used_at=timezone.now())
        return cls.objects.create(
            user=user,
            token=cls.generate_token(),
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
            requested_ip=ip,
            requested_user_agent=(user_agent or "")[:512],
        )

    @classmethod
    def consume(cls, token):
        """Atomic lookup + mark-used. Returns row on success, None otherwise."""
        from django.db import transaction
        with transaction.atomic():
            # SELECT FOR UPDATE prevents two concurrent confirms reusing the same token
            row = (cls.objects
                   .select_for_update()
                   .filter(token=token, used=False, expires_at__gt=timezone.now())
                   .first())
            if row is None:
                return None
            row.mark_as_used()
            return row

    @classmethod
    def cleanup_expired(cls):
        """Periodic janitor — drop expired rows."""
        expired = cls.objects.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        return count