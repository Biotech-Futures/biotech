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
from .permissions import IsMentorAdminOrSupervisor
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime
from django.core.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .services.roles import revoke_role, grant_role, create_role
from django.contrib.auth import get_user_model

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

    def create(self, request, *args, **kwargs):
        """
        Create a new role using the service layer.
        This ensures both the Role and Django Group are created together.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Use service layer to create role (handles both Role and Group creation)
            role = create_role(serializer.validated_data['role_name'])

            # Return serialized response
            response_serializer = self.get_serializer(role)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class RoleAssignmentHistoryViewSet(mixins.UpdateModelMixin,
                                  viewsets.ReadOnlyModelViewSet):
    serializer_class = RoleAssignmentHistorySerializer

    def get_permissions(self):
        # Admin-only actions
        if self.action in ('grant_role', 'revoke_role', 'partial_update'):
            return [permissions.IsAdminUser()]
        # All other actions require authentication
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
            result = grant_role(user, role, start=start_date, revoke_others=revoke_others, force=force)
            
            response_data = {
                "message": result.get('message', f"Role '{role.role_name}' granted to user '{user.email}'"),
                "action_taken": result.get('action_taken'),
                "details": {
                    "user_id": user.id,
                    "role_id": role.id,
                    "start_time": start_date or timezone.now(),
                    "user_groups": list(user.groups.values_list('name', flat=True)),
                    "granted_role": result['granted_role'],
                    "revoked_roles": result['revoked_roles'],
                    "had_existing_roles": result['had_existing'],
                    "duplicate_role": result.get('duplicate_role', False)
                }
            }
            
            # Add warning if roles were revoked
            if result['revoked_roles']:
                response_data["warning"] = f"Revoked existing roles: {', '.join(result['revoked_roles'])}"
            
            if result.get('duplicate_role') and not force:
                response_data["info"] = "User already had this role - extended the duration instead of creating duplicate"
            
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
    
    def get_page_size(self, request):
        """Override to add debugging and ensure page_size works"""
        if self.page_size_query_param:
            # Handle both Django and DRF requests
            if hasattr(request, 'query_params'):
                page_size = request.query_params.get(self.page_size_query_param)
            else:
                page_size = request.GET.get(self.page_size_query_param)
            
            if page_size is not None:
                try:
                    page_size = int(page_size)
                    if page_size > 0:
                        return min(page_size, self.max_page_size)
                except (KeyError, ValueError):
                    pass
        return self.page_size

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
        ).select_related('uploader_user_id').prefetch_related('resourceroles__role') # Resources → ResourceRoles → Roles
        
        # Only apply role-based filtering for list actions
        # For retrieve/detail actions, we handle permissions in the retrieve() method
        if self.action == 'list' and not user.is_staff:
            # Regular users can only see resources they uploaded or resources visible to their roles
            queryset = queryset.filter(
                Q(uploader_user_id=user) |  # Resources they uploaded
                Q(resourceroles__role__in=user_roles)  # Resources visible to their roles
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
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only mentors, admins, and supervisors can create, modify, or delete resources
            return [IsMentorAdminOrSupervisor()]
        else:
            # List and retrieve require authentication
            return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Automatically set uploader to the authenticated user - users can only upload as themselves"""
        # Only set user if not already provided in the data
        if 'uploader_user_id' not in serializer.validated_data:
            serializer.save(uploader_user_id=self.request.user)
        else:
            serializer.save()
    
    def perform_update(self, serializer):
        """Handle file updates - delete old file if new one is uploaded"""
        instance = self.get_object()
        
        # Check if a new file is being uploaded
        if 'resource_file' in self.request.FILES:
            # Delete old file from blob storage if it exists
            if instance.resource_file:
                try:
                    instance.resource_file.delete(save=False)
                except Exception as e:
                    # Log error but continue with update
                    print(f"Error deleting old file: {e}")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Soft delete and optionally delete file from blob storage"""
        instance.deleted_flag = True
        instance.deleted_datetime = timezone.now()
        
        # Optionally delete the file from blob storage
        # Uncomment if you want to delete files when resource is soft-deleted
        # if instance.resource_file:
        #     try:
        #         instance.resource_file.delete(save=False)
        #     except Exception as e:
        #         print(f"Error deleting file: {e}")
        
        instance.save()

    def retrieve(self, request, *args, **kwargs):
        """Get single resource with visibility check"""
        instance = self.get_object()
        
        # Check if user has access to this resource
        can_access, reason = self._user_can_access_resource(request.user, instance)
        if not can_access:
            return Response(
                {
                    "error": "Permission denied",
                    "detail": reason
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def _user_can_access_resource(self, user, resource):
        """
        Check if user can access a specific resource.
        Returns (bool, str): (can_access, reason_message)
        """
        # Admins can access everything
        if user.is_staff:
            return True, "Admin access granted"
        
        # Users can access resources they uploaded
        if resource.uploader_user_id == user:
            return True, "Access granted as uploader"
        
        # Check if user has any of the required roles
        user_roles = self._get_user_roles(user)
        
        # Get resource roles using the correct field name
        from apps.resources.models import ResourceRoles
        resource_role_objects = ResourceRoles.objects.filter(resource=resource).select_related('role')
        resource_roles = [rr.role for rr in resource_role_objects]
        resource_role_names = [rr.role_name for rr in resource_roles]
        
        # Check if user has any matching role
        user_role_objects = list(user_roles)
        has_access = any(role in [rr.id for rr in resource_roles] for role in user_role_objects)
        
        if has_access:
            return True, "Access granted based on user role"
        
        # No access - provide detailed reason
        if not resource_role_names:
            reason = "This resource has no role restrictions, but you are not the uploader."
        else:
            # Get user's role names for the error message
            from apps.resources.models import RoleAssignmentHistory
            now = timezone.now()
            user_role_names = list(RoleAssignmentHistory.objects.filter(
                user=user,
                valid_from__lte=now,
                valid_to__isnull=True
            ).values_list('role__role_name', flat=True))
            
            reason = (
                f"This resource is restricted to users with the following role(s): {', '.join(resource_role_names)}. "
                f"Your current role(s): {', '.join(user_role_names) if user_role_names else 'None'}."
            )
        
        return False, reason

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

