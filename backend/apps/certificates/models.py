# CERTIFICATES MODELS

from django.db import models

class CertificateType(models.Model):
    certificate_type_id = models.AutoField(primary_key=True) # Auto-incrementing primary key might be optional apparently django does auto primary keys automatically
    certificate_type = models.CharField(unique=True, max_length=255)
    requires_number = models.BooleanField()
    requires_expiry = models.BooleanField()

    class Meta:
        db_table = 'certificate_type'
        index = models.Index(fields=['certificate_type'])

class MentorCertificate(models.Model):
    certificate_id = models.AutoField(primary_key=True) # Auto-incrementing primary key
    certificate_type = models.ForeignKey(CertificateType, on_delete=models.PROTECT) # Protect to prevent deletion if referenced by other mentore certificates
    mentor_profile = models.ForeignKey('users.MentorProfile', on_delete=models.CASCADE) # Cascade to delete mentor certificates if the mentor profile is deleted - also renamed to mentor_profile for clarity
    certificate_number = models.CharField(max_length=255, blank=True, null=True)
    issued_by = models.CharField(max_length=255)
    issued_at = models.DateField()
    expires_at = models.DateField(blank=True, null=True)
    file_url = models.URLField(max_length=500, blank=True, null=True) # URLField for file URL
    verified = models.BooleanField(default=False) # Changed to default False for better security
    def __str__(self):
        return f"{self.mentor_profile} - {self.certificate_type}" # String representation for easier identification

    class Meta:
        db_table = 'mentor_certificate'
        verbose_name = "Mentor Certificate"
        verbose_name_plural = "Mentor Certificates" # Just added some verbose names for better admin readability
        index = models.Index(fields=['mentor_profile', 'certificate_type'])
