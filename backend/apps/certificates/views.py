# views.py
from rest_framework import mixins, permissions, viewsets
from .models import MentorCertificate
from .serializers import MentorCertificateSerializer, MentorCertificateCreateSerializer

class MentorCertificateViewSet(mixins.RetrieveModelMixin,
                               mixins.CreateModelMixin,
                               viewsets.GenericViewSet):
    """
    GET /certificates/v1/{id}/   -> retrieve (admin only)
    POST /certificates/v1/       -> create (admin only)
    """
    queryset = MentorCertificate.objects.select_related("certificate_type", "mentor_profile")
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        if self.action == "create":
            return MentorCertificateCreateSerializer
        return MentorCertificateSerializer
