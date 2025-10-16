# Create your views here.
from rest_framework import mixins, permissions, viewsets
from .models import MentorCertificate
from .serializers import MentorCertificateSerializer, MentorCertificateCreateSerializer


class MentorCertificateViewSet(mixins.RetrieveModelMixin,
                               mixins.CreateModelMixin,
                               viewsets.GenericViewSet):
    """
    GET /certificates/v1/{id}/  -> retrieve a single certificate (admin-only)
    POST /certificates/v1/      -> create a new certificate (admin-only)
    """
    queryset = MentorCertificate.objects.select_related(
        "certificate_type", "mentor_profile"
    )
    permission_classes = [permissions.IsAdminUser]  # admin/staff only
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions:
        - Create: MentorCertificateCreateSerializer
        - Retrieve: MentorCertificateSerializer
        """
        if self.action == 'create':
            return MentorCertificateCreateSerializer
        return MentorCertificateSerializer
