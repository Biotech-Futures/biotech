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
# ================================Testing RevokeEndpoint (TO BE DELETED)==============================================
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .services.roles import revoke_role, grant_role
from django.contrib.auth import get_user_model
# ================================Testing RevokeEndpoint (TO BE DELETED)==============================================

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

class RoleAssignmentHistoryViewSet(mixins.UpdateModelMixin,
                                  viewsets.ReadOnlyModelViewSet):
    serializer_class = RoleAssignmentHistorySerializer

    def get_permissions(self):
        if self.request.method in ("PATCH",):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

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

        # Aware filter window (prevents naive datetime warnings)
        v_from = parse_date(v_from_s) if v_from_s else None
        v_to   = parse_date(v_to_s) if v_to_s else None
        if v_from:
            v_from = timezone.make_aware(datetime.combine(v_from, datetime.min.time()))
        if v_to:
            v_to = timezone.make_aware(datetime.combine(v_to, datetime.min.time()))

        if v_from and not v_to:
            qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gte=v_from))
        if v_to and not v_from:
            qs = qs.filter(valid_from__lte=v_to)
        if v_from and v_to:
            qs = qs.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=v_from),
                Q(valid_from__lte=v_to),
            )

        return qs.order_by("user_id", "role_id", "valid_from")

    # Optional: prevent edits to closed (historical) rows
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.valid_to and instance.valid_to < timezone.now():
            return Response(
                {"detail": "Cannot modify a closed assignment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    # ================================Testing RevokeEndpoint (TO BE DELETED)==============================================
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def revoke_role(self, request):
        """
        Test the revoke_django_role function
        POST /resources/role-assignments/revoke_role/
        Body: {
            "user_id": 1,
            "role_id": 2,
            "end": "2024-06-30T10:30:00Z"  # optional
        }
        """
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        end_date = request.data.get('end')
        
        if not user_id or not role_id:
            return Response(
                {"error": "user_id and role_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            User = get_user_model()
            user = User.objects.get(id=user_id)
            role = Roles.objects.get(id=role_id)
            
            # Parse end date if provided
            if end_date:
                from django.utils.dateparse import parse_datetime
                end_date = parse_datetime(end_date)
            
            # Call your revoke_role function
            revoke_role(user, role, end=end_date)
            
            return Response(
                {
                    "message": f"Role '{role.role_name}' revoked from user '{user.email}'",
                    "details": {
                        "user_id": user.id,
                        "role_id": role.id,
                        "end_time": end_date or timezone.now(),
                        "user_groups": list(user.groups.values_list('name', flat=True))
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def grant_role(self, request):
        """
        Test the grant_role function
        POST /resources/role-assignments/grant_role/
        Body: {
            "user_id": 1,
            "role_id": 2,
            "start": "2024-01-01T10:30:00Z"  # optional
        }
        """
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        start_date = request.data.get('start')
        
        if not user_id or not role_id:
            return Response(
                {"error": "user_id and role_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            User = get_user_model()
            user = User.objects.get(id=user_id)
            role = Roles.objects.get(id=role_id)
            
            # Parse start date if provided
            if start_date:
                from django.utils.dateparse import parse_datetime
                start_date = parse_datetime(start_date)
            
            # Call the grant_role function
            grant_role(user, role, start=start_date)
            
            return Response(
                {
                    "message": f"Role '{role.role_name}' granted to user '{user.email}'",
                    "details": {
                        "user_id": user.id,
                        "role_id": role.id,
                        "start_time": start_date or timezone.now(),
                        "user_groups": list(user.groups.values_list('name', flat=True))
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )