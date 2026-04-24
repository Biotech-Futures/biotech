from rest_framework import mixins, permissions, viewsets

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("actor_user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
    http_method_names = ["get", "head", "options"]

