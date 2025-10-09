# CERTIFICATES MODELS

from django.db import models
from django.db.models import Q
from django.db import connection

class CertificateType(models.Model):
    certificate_type = models.CharField(unique=True, max_length=255)
    requires_number = models.BooleanField(default=False)
    requires_expiry = models.BooleanField(default=False)

    class Meta:
        db_table = 'certificate_type'
        indexes = [
            models.Index(fields=['certificate_type'])
        ]
        
    
    def __str__(self):
        return self.certificate_type

class MentorCertificate(models.Model):
    certificate_type = models.ForeignKey(CertificateType, on_delete=models.PROTECT) # Protect to prevent deletion if referenced by other mentore certificates
    mentor_profile = models.ForeignKey('users.MentorProfile', on_delete=models.CASCADE) # Cascade to delete mentor certificates if the mentor profile is deleted - also renamed to mentor_profile for clarity
    certificate_number = models.CharField(max_length=255, blank=True, null=True)
    issued_by = models.CharField(max_length=255)
    issued_at = models.DateField()
    expires_at = models.DateField(blank=True, null=True)
    file_url = models.URLField(max_length=500, blank=True, null=True) # URLField for file URL
    verified = models.BooleanField(default=False) # Changed to default False for better security

    class Meta:
        db_table = 'mentor_certificate'
        verbose_name = "Mentor Certificate"
        verbose_name_plural = "Mentor Certificates"
        indexes = [
            models.Index(fields=['mentor_profile', 'certificate_type'])
        ]
        constraints = [
            # Ensure a mentor cannot have duplicate certificates of the same type with the same number
            models.UniqueConstraint(
                fields=['mentor_profile', 'certificate_type', 'certificate_number'],
                name='unique_certificate_per_mentor'
            ),
        ]

        # ✅ Conditional constraint — apply time-based check only if NOT SQLite
        if connection.vendor != "sqlite":
            constraints += [
                models.CheckConstraint(
                    condition=Q(expires_at__isnull=True) | Q(expires_at__gte=models.functions.Now()) | Q(verified=False),
                    name='cannot_verify_expired_certificate'
                )
            ]
    
    def __str__(self):
        return f"{self.mentor_profile} - {self.certificate_type}" # String representation for easier identification
