from django.contrib import admin
from .models import CertificateType, MentorCertificate

# Register your models here.
admin.site.register(CertificateType)
admin.site.register(MentorCertificate)
