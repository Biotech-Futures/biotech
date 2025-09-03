# CERTIFICATES MODELS

from django.db import models

class CertificateType(models.Model):
    certificate_type_id = models.IntegerField(primary_key=True)
    certificate_type = models.CharField(unique=True, max_length=255)
    requires_number = models.BooleanField()
    requires_expiry = models.BooleanField()

    class Meta:
        db_table = 'certificate_type'

class MentorCertificate(models.Model):
    certificate_id = models.IntegerField(primary_key=True)
    certificate_type = models.ForeignKey(CertificateType, models.DO_NOTHING)
    user = models.ForeignKey('MentorProfile', models.DO_NOTHING)
    certificate_number = models.CharField(max_length=255, blank=True, null=True)
    issued_by = models.CharField(max_length=255)
    issued_at = models.DateField()
    expires_at = models.DateField(blank=True, null=True)
    file_url = models.CharField(max_length=255, blank=True, null=True)
    verified = models.BooleanField()

    class Meta:
        db_table = 'mentor_certificate'
