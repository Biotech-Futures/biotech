# from django.shortcuts import render
# from rest_framework import viewsets
# from rest_framework.permissions import IsAuthenticated
# from .models import Roles, RoleAssignmentHistory
# from .serializers import RoleSerializer, RoleAssignmentHistorySerializer

# from django.db.models import Q
# from datetime import datetime
# from django.utils import timezone
# from django.utils.dateparse import parse_date
# from rest_framework import permissions

# class RoleViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Roles.objects.all().order_by('role_name')
#     serializer_class = RoleSerializer
#     permission_classes = [IsAuthenticated]
#     ordering = ['role_name']
#     http_method_names = ["get", "post", "patch", "delete", "head", "options"]

#     def get_permissions(self):
#         if self.request.method in ("POST", "PATCH", "DELETE"):
#             return [IsAdminUser()]
#         return [IsAuthenticated()]

from rest_framework import mixins, viewsets, permissions
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Roles, RoleAssignmentHistory
from .serializers import RoleSerializer, RoleAssignmentHistorySerializer
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime

class RoleViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """
    GET    /.../roles/           (list)
    GET    /.../roles/{id}/      (retrieve)
    POST   /.../roles/           (create)
    PATCH  /.../roles/{id}/      (partial update)
    DELETE /.../roles/{id}/      (destroy)
    """
    queryset = Roles.objects.all().order_by("role_name")
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.request.method in ("POST", "PATCH", "DELETE"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

class RoleAssignmentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RoleAssignmentHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = (RoleAssignmentHistory.objects
              .select_related("user", "role")
              .all())

        p = self.request.query_params
        user_id = p.get("user_id")
        role_id = p.get("role_id")
        v_from_s = p.get("valid_from")
        v_to_s   = p.get("valid_to")

        if user_id:
            qs = qs.filter(user_id=user_id)
        if role_id:
            qs = qs.filter(role_id=role_id)

        v_from = parse_date(v_from_s) if v_from_s else None
        v_to   = parse_date(v_to_s) if v_to_s else None

        # Date conversion to make aware datetime
        if v_from:
            v_from = timezone.make_aware(datetime.combine(v_from, datetime.min.time()))

        if v_to:
            v_to = timezone.make_aware(datetime.combine(v_to, datetime.min.time()))

        if v_from and not v_to: # only valid_from provided: keep rows that have not ended before v_from
            qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gte=v_from))

        if v_to and not v_from: # only valid_to provided: keep rows that started on/before v_to
            qs = qs.filter(valid_from__lte=v_to)

        if v_from and v_to: # both provided: interval overlap with [v_from, v_to]
            qs = qs.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=v_from),
                Q(valid_from__lte=v_to),
            )

        return qs.order_by("user_id", "role_id", "valid_from")