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

from rest_framework import mixins, viewsets, permissions, status, pagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Roles, RoleAssignmentHistory, Resources, ResourceRoles
from .serializers import RoleSerializer, RoleAssignmentHistorySerializer, ResourcesSerializer, ResourceListSerializer
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

    # ================================ Role Management Actions ==============================================
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def grant_role(self, request):
        """
        Grant a role to a user with conflict resolution options
        POST /resources/role-assignments/grant_role/
        Body: {
            "user_id": 1,
            "role_id": 2,
            "start": "2024-01-01T10:30:00Z",  # optional
            "revoke_others": true,  # optional, defaults to true
            "force": false  # optional, if true, bypasses existing role checks
        }
        """
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        start_date = request.data.get('start')
        revoke_others = request.data.get('revoke_others', True)  # Default to True
        force = request.data.get('force', False)  # Default to False
        
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
            
            # Check for existing active roles if not forcing
            if not force:
                active_roles = RoleAssignmentHistory.objects.filter(
                    user=user,
                    valid_to__isnull=True
                ).exclude(role=role)
                
                if active_roles.exists() and not revoke_others:
                    active_role_names = [ar.role.role_name for ar in active_roles]
                    return Response(
                        {
                            "error": "User already has active roles",
                            "existing_roles": active_role_names,
                            "suggestion": "Set 'revoke_others': true to revoke existing roles, or 'force': true to allow multiple roles"
                        },
                        status=status.HTTP_409_CONFLICT
                    )
            
            # Call the grant_role function
            result = grant_role(user, role, start=start_date, revoke_others=revoke_others)
            
            response_data = {
                "message": f"Role '{role.role_name}' granted to user '{user.email}'",
                "details": {
                    "user_id": user.id,
                    "role_id": role.id,
                    "start_time": start_date or timezone.now(),
                    "user_groups": list(user.groups.values_list('name', flat=True)),
                    "granted_role": result['granted_role'],
                    "revoked_roles": result['revoked_roles'],
                    "had_existing_roles": result['had_existing']
                }
            }
            
            # Add warning if roles were revoked
            if result['revoked_roles']:
                response_data["warning"] = f"Revoked existing roles: {', '.join(result['revoked_roles'])}"
            
            return Response(response_data, status=status.HTTP_200_OK)
            
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
    def revoke_role(self, request):
        """
        Revoke a role from a user
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
            
            # Call the revoke_role function
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


# ================RESOURCES API================
# Pagination class for resources
class ResourcesPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ResourcesViewSet(mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.DestroyModelMixin,
                      viewsets.GenericViewSet):
    """
    Resources CRUD API:
    
    POST   /resources/           (create)
    GET    /resources/           (List)
    GET    /resources/{id}/      (Retrieve one resource)
    PATCH  /resources/{id}/      (Update)
    DELETE /resources/{id}/      (Delete)
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = ResourcesPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        """Use different serializers for list vs detail(ResourceListSerializer for list, ResourcesSerializer for detail)"""
        if self.action == 'list':
            return ResourceListSerializer
        return ResourcesSerializer

    def get_queryset(self):
        """Filter resources based on user permissions and query params"""
        user = self.request.user
        
        # Get user's current roles
        user_roles = self._get_user_roles(user)
        
        # Base queryset - only non-deleted resources
        queryset = Resources.objects.filter(
            deleted_flag=False
        ).select_related('uploader_user_id').prefetch_related('resourceroles_set__role') # Resources → ResourceRoles → Roles
        
        # Filter by user's role access
        if not user.is_staff:
            # Regular users can only see resources they uploaded or resources visible to their roles
            queryset = queryset.filter(
                Q(uploader_user_id=user) |  # Resources they uploaded
                Q(resourceroles_set__role__in=user_roles)  # Resources visible to their roles
            ).distinct()
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        
        return queryset.order_by('-upload_datetime')

    def _get_user_roles(self, user):
        """Get user's current active roles"""
        now = timezone.now()
        return RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).values_list('role', flat=True)

    def _apply_filters(self, queryset):
        """Apply query parameter filters"""
        params = self.request.query_params
        
        # Filter by uploader
        uploader_id = params.get('uploader_id')
        if uploader_id:
            queryset = queryset.filter(uploader_user_id=uploader_id)
        
        # Filter by role (group)
        role = params.get('role')
        if role:
            queryset = queryset.filter(resource_roles__role__role_name__icontains=role)
        
        # Search in name and description
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(resource_name__icontains=search) |
                Q(resource_description__icontains=search)
            )
        
        # Order by
        order = params.get('order', 'newest')
        if order == 'oldest':
            queryset = queryset.order_by('upload_datetime')
        elif order == 'name':
            queryset = queryset.order_by('resource_name')
        elif order == 'newest':
            queryset = queryset.order_by('-upload_datetime')
        
        return queryset

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create']:
            # Only authenticated users can create resources
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            # Only admins can update resource metadata and roles
            return [IsAdminUser()]
        elif self.action in ['destroy']:
            # Only admins can soft delete
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Set uploader to current user"""
        serializer.save(uploader_user_id=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """Get single resource with visibility check"""
        instance = self.get_object()
        
        # Check if user has access to this resource
        if not self._user_can_access_resource(request.user, instance):
            return Response(
                {"detail": "You don't have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def _user_can_access_resource(self, user, resource):
        """Check if user can access a specific resource"""
        # Admins can access everything
        if user.is_staff:
            return True
        
        # Users can access resources they uploaded
        if resource.uploader_user_id == user:
            return True
        
        # Check if user has any of the required roles
        user_roles = self._get_user_roles(user)
        resource_roles = resource.resource_roles.values_list('role', flat=True)
        
        return any(role in resource_roles for role in user_roles)

    def destroy(self, request, *args, **kwargs):
        """Soft delete resource"""
        instance = self.get_object()
        instance.deleted_flag = True
        instance.deleted_datetime = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    # ================================ ResourceRole Management Actions ==============================================
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign_role(self, request, pk=None):
        """Assign a role to this resource (Admin only)"""
        resource = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {"error": "role_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Roles.objects.get(id=role_id)
            
            # Check if already assigned
            if ResourceRoles.objects.filter(resource=resource, role=role).exists():
                return Response(
                    {"error": "Role is already assigned to this resource"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ResourceRoles.objects.create(resource=resource, role=role)
            
            return Response({
                "message": f"Role '{role.role_name}' assigned to resource '{resource.resource_name}'",
                "resource_id": resource.id,
                "role_id": role.id
            }, status=status.HTTP_201_CREATED)
            
        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['delete'], permission_classes=[IsAdminUser])
    def remove_role(self, request, pk=None):
        """Remove a role from this resource (Admin only)"""
        resource = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {"error": "role_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Roles.objects.get(id=role_id)
            resource_role = ResourceRoles.objects.get(resource=resource, role=role)
            role_name = role.role_name
            resource_role.delete()
            
            return Response({
                "message": f"Role '{role_name}' removed from resource '{resource.resource_name}'"
            }, status=status.HTTP_200_OK)
            
        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ResourceRoles.DoesNotExist:
            return Response(
                {"error": "Role is not assigned to this resource"},
                status=status.HTTP_404_NOT_FOUND
            )

