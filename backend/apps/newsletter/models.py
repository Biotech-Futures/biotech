from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string

class NewsletterSubscription(models.Model):
  """Newsletter email subscription record.

  Notes:
  - Email is normalized to lowercase on save to enforce case-insensitive uniqueness.
  - User link is optional and preserved on user deletion (SET_NULL) so that
    subscriptions can outlive user accounts if needed.
  - subscribed_at/unsubscribed_at are managed automatically when state changes.
  - unsubscribe_token can support one-click unsubscribe links.
  """

  email = models.EmailField(unique=True, db_index=True)
  # even if user is deleted, we'll keep the email in our records
  user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="newsletter_subscriptions",
  )
  is_subscribed = models.BooleanField(default=True)
  subscribed_at = models.DateTimeField(null=True, blank=True)
  unsubscribed_at = models.DateTimeField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  unsubscribe_token = models.CharField(
    max_length=128, blank=True, null=True, unique=True
  )  # for link based unsubscribe

  class Meta:
    db_table = "newsletter_subscription"
    verbose_name = "Newsletter Subscription"
    verbose_name_plural = "Newsletter Subscriptions"
    indexes = [
      models.Index(fields=["is_subscribed"]),
    ]

  def __str__(self) -> str:  # pragma: no cover - trivial
    state = "subscribed" if self.is_subscribed else "unsubscribed"
    return f"{self.email} ({state})"

  def clean(self):
    # Normalize email in clean as well (admin/forms)
    if self.email:
      self.email = self.email.strip().lower()
    # Coherence between flags and timestamps
    if self.is_subscribed and self.unsubscribed_at is not None:
      raise ValidationError({
        "unsubscribed_at": "unsubscribed_at must be null when is_subscribed is True."
      })

  def _ensure_unsubscribe_token(self):
    if not self.unsubscribe_token:
      # 48-char URL-safe token; ensure uniqueness in rare collision
      for _ in range(3):
        token = get_random_string(48)
        if not NewsletterSubscription.objects.filter(unsubscribe_token=token).exists():
          self.unsubscribe_token = token
          break

  def save(self, *args, **kwargs):
    # Normalize email always
    if self.email:
      self.email = self.email.strip().lower()

    # Determine state transitions to manage timestamps
    now = timezone.now()
    if self.pk:
      prev = NewsletterSubscription.objects.filter(pk=self.pk).only(
        "is_subscribed", "subscribed_at", "unsubscribed_at"
      ).first()
    else:
      prev = None

    # If new and subscribed with no timestamp, set subscribed_at
    if not prev and self.is_subscribed and not self.subscribed_at:
      self.subscribed_at = now

    # On toggle to subscribed
    if prev and not prev.is_subscribed and self.is_subscribed:
      self.subscribed_at = now
      self.unsubscribed_at = None

    # On toggle to unsubscribed
    if prev and prev.is_subscribed and not self.is_subscribed:
      self.unsubscribed_at = now

    # Always ensure we have a token
    self._ensure_unsubscribe_token()

    super().save(*args, **kwargs)

  # Convenience methods for idempotent operations
  @classmethod
  def subscribe(cls, email: str, user=None):
    """Idempotently subscribe an email. Returns (instance, created_or_updated: bool).

    - Normalizes email to lowercase.
    - Links user if provided and not already linked.
    """
    email_norm = (email or "").strip().lower()
    obj, created = cls.objects.get_or_create(
      email=email_norm,
      defaults={
        "user": user,
        "is_subscribed": True,
        "subscribed_at": timezone.now(),
      },
    )
    changed = created
    if not created:
      if not obj.is_subscribed:
        obj.is_subscribed = True
        obj.subscribed_at = timezone.now()
        obj.unsubscribed_at = None
        changed = True
      if user and obj.user is None:
        obj.user = user
        changed = True
      if changed:
        obj.save(update_fields=[
          "is_subscribed", "subscribed_at", "unsubscribed_at", "user", "updated_at"
        ])
    return obj, changed

  @classmethod
  def unsubscribe(cls, *, email: str | None = None, token: str | None = None):
    """Idempotently unsubscribe by email or token. Returns (instance or None, changed: bool).

    Returns (None, False) if no matching record is found to avoid account enumeration.
    """
    if not email and not token:
      raise ValidationError("Provide email or token to unsubscribe.")

    obj = None
    if token:
      obj = cls.objects.filter(unsubscribe_token=token).first()
    if not obj and email:
      obj = cls.objects.filter(email=(email or "").strip().lower()).first()

    if not obj:
      return None, False

    if not obj.is_subscribed:
      return obj, False

    obj.is_subscribed = False
    obj.unsubscribed_at = timezone.now()
    obj.save(update_fields=["is_subscribed", "unsubscribed_at", "updated_at"])
    return obj, True



