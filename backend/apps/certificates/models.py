# CERTIFICATES MODELS

from django.conf import settings
from django.db import models


class CertificateType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    requires_number = models.BooleanField(default=False)
    requires_expiry = models.BooleanField(default=False)

    class Meta:
        db_table = "certificate_type"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class MentorCertificate(models.Model):
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.PROTECT,
    )
    mentor_profile = models.ForeignKey(
        "users.MentorProfile",
        on_delete=models.CASCADE,
    )
    certificate_number = models.CharField(max_length=255, blank=True, null=True)
    issued_by = models.CharField(max_length=255)
    issued_at = models.DateField()
    expires_at = models.DateField(blank=True, null=True)
    file_url = models.URLField(max_length=500, blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates_verified",
    )

    class Meta:
        db_table = "mentor_certificate"
        verbose_name = "Mentor Certificate"
        verbose_name_plural = "Mentor Certificates"
        indexes = [
            models.Index(fields=["mentor_profile", "certificate_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["mentor_profile", "certificate_type", "certificate_number"],
                name="unique_certificate_per_mentor",
            ),
        ]

    def __str__(self):
        return f"{self.mentor_profile} - {self.certificate_type}"
