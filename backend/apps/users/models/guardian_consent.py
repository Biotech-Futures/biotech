from django.conf import settings
from django.db import models


class GuardianConsentRequest(models.Model):
    """A consent link emailed to a student's guardian.

    Only a hash of the token is stored, so the table can't be used to open
    links. A link works once, until it expires, and only while it's the newest
    one for the student: sending another revokes it.
    """

    student = models.ForeignKey(
        "StudentProfile", on_delete=models.CASCADE, related_name="consent_requests",
    )
    # sha256 hex of the token in the emailed link.
    token_hash = models.CharField(max_length=64, unique=True)
    # The guardian it was sent to, as they were when it was sent. The link stops
    # working if the student's guardian changes afterwards.
    guardian_first_name = models.CharField(max_length=255, blank=True, default="")
    guardian_last_name = models.CharField(max_length=255, blank=True, default="")
    guardian_email = models.EmailField()
    # Sent to a requested guardian change rather than the guardian on file.
    for_pending_guardian = models.BooleanField(default=False)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "guardian_consent_request"
        indexes = [models.Index(fields=["student", "-created_at"])]


class GuardianConsent(models.Model):
    """A consent form a guardian signed on the platform: what they agreed to,
    their media-consent answer and their drawn signature. Rows are kept after a
    withdrawal so the history stays complete."""

    student = models.ForeignKey(
        "StudentProfile", on_delete=models.CASCADE, related_name="consents",
    )
    request = models.OneToOneField(
        GuardianConsentRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="consent",
    )
    guardian_full_name = models.CharField(max_length=255)
    guardian_email = models.EmailField()
    media_consent = models.BooleanField()
    # The drawn signature as a PNG.
    signature_png = models.BinaryField()
    # Which wording of the consent form was shown (apps/users/consent_form.py).
    consent_version = models.CharField(max_length=32)
    signed_at = models.DateTimeField(auto_now_add=True)
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_user_agent = models.CharField(max_length=512, blank=True, default="")
    # Where the signed record (PDF) is kept in the guardian-consent-forms container. Blank
    # until it's been stored; it can always be rebuilt from this row.
    record_pdf_key = models.CharField(max_length=255, blank=True, default="")
    # Recorded by an admin when the guardian withdraws, by contacting support.
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    media_withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "guardian_consent"
        indexes = [models.Index(fields=["student", "-signed_at"])]

    @property
    def reference(self) -> str:
        """Shown as the consent response ID, alongside Qualtrics response IDs."""
        return f"BTF-{self.pk}"
