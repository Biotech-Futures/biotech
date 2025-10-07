from django.shortcuts import render

# Create your views here.
from rest_framework import mixins, permissions, viewsets
from .models import MentorCertificate
from .serializers import MentorCertificateSerializer

class MentorCertificateViewSet(mixins.RetrieveModelMixin,
                               viewsets.GenericViewSet):
    """
    GET /certificates/v1/{id}/  -> retrieve a single certificate (admin-only)
    """
    queryset = MentorCertificate.objects.select_related(
        "certificate_type", "mentor_profile"
    )
    serializer_class = MentorCertificateSerializer
    permission_classes = [permissions.IsAdminUser]  # admin/staff only
