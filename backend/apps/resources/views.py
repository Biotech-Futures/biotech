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
from .models import Roles, RoleAssignmentHistory, Resources, ResourceAudience
from .serializers import (
    RoleSerializer,
    RoleAssignmentHistorySerializer,
    ResourceAccessSerializer,
    ResourcesSerializer,
    ResourceListSerializer,
    ResourceTypeSerializer,
)
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
from apps.audit.services import log_audit_event
from django.http import HttpResponseRedirect
from .models import ResourceType

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
    queryset = Resources.objects.select_related('uploaded_by', 'track').prefetch_related('audiences__role', 'audiences__track').all()

    def get_serializer_class(self):
        """Use different serializers for list vs detail(ResourceListSerializer for list, ResourcesSerializer for detail)"""
        if self.action == 'list':
            return ResourceListSerializer
        return ResourcesSerializer

    def get_queryset(self):
        """Filter resources based on user permissions and query params"""
        user = self.request.user

        if not user or not user.is_authenticated:
            return Resources.objects.none()
        
        # Get user's current roles
        user_roles = self._get_user_roles(user)
        
        # Base queryset - only non-deleted resources
        queryset = Resources.objects.filter(
            deleted_at__isnull=True
        ).select_related('uploaded_by', 'track').prefetch_related('audiences__role', 'audiences__track')
        
        # Only apply role-based filtering for list actions
        # For retrieve/detail actions, we handle permissions in the retrieve() method
        if self.action == 'list' and not user.is_staff:
            # Regular users can only see resources they uploaded or resources visible to their roles
            access_filter = (
                Q(uploaded_by=user) |  # Resources they uploaded
                Q(visibility_scope=Resources.VisibilityScope.PUBLIC)
                | Q(audiences__role__in=user_roles)
            )
            if user.track_id:
                access_filter |= Q(audiences__track_id=user.track_id)
            queryset = queryset.filter(access_filter).distinct()
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        
        return queryset.order_by('-uploaded_at')

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
            queryset = queryset.filter(uploaded_by_id=uploader_id)
        
        # Filter by role (group)
        role = params.get('role')
        if role:
            queryset = queryset.filter(audiences__role__role_name__icontains=role)

        track_id = params.get("track_id")
        if track_id:
            queryset = queryset.filter(
                Q(track_id=track_id) | Q(audiences__track_id=track_id)
            )
        
        # Search in name and description
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Order by
        order = params.get('order', 'newest')
        if order == 'oldest':
            queryset = queryset.order_by('uploaded_at')
        elif order == 'name':
            queryset = queryset.order_by('name')
        elif order == 'newest':
            queryset = queryset.order_by('-uploaded_at')
        
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
        """Automatically set uploader to the authenticated user - users can only upload as themselves"""
        resource = serializer.save(uploaded_by=self.request.user)
        log_audit_event(
            actor=self.request.user,
            entity_type="resource",
            entity_id=resource.id,
            action="create",
            after_state=ResourcesSerializer(resource).data,
        )

    def perform_update(self, serializer):
        resource = self.get_object()
        before_state = ResourcesSerializer(resource).data
        resource = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="resource",
            entity_id=resource.id,
            action="update",
            before_state=before_state,
            after_state=ResourcesSerializer(resource).data,
        )

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
        if resource.uploaded_by == user:
            return True, "Access granted as uploader"

        if resource.visibility_scope == Resources.VisibilityScope.PUBLIC:
            return True, "Access granted because the resource is public"
        
        # Check if user has any of the required roles
        user_roles = self._get_user_roles(user)
        
        # Get resource roles using the correct field name
        audiences = ResourceAudience.objects.filter(resource=resource).select_related("role", "track")
        resource_role_names = [aud.role.role_name for aud in audiences if aud.role_id]
        resource_track_names = [aud.track.track_name for aud in audiences if aud.track_id]

        user_role_objects = set(user_roles)
        role_access = any(aud.role_id in user_role_objects for aud in audiences if aud.role_id)
        track_access = any(aud.track_id == user.track_id for aud in audiences if aud.track_id and user.track_id)

        if role_access or track_access:
            return True, "Access granted based on audience scope"
        
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
            ).filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=now)
            ).values_list('role__role_name', flat=True))
            
            reason = (
                f"This resource is restricted to users with the following role(s): {', '.join(resource_role_names)}. "
                f"Track scope(s): {', '.join(resource_track_names) if resource_track_names else 'None'}. "
                f"Your current role(s): {', '.join(user_role_names) if user_role_names else 'None'}."
            )
        
        return False, reason

    def destroy(self, request, *args, **kwargs):
        """Soft delete resource"""
        instance = self.get_object()
        before_state = ResourcesSerializer(instance).data
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])
        log_audit_event(
            actor=request.user,
            entity_type="resource",
            entity_id=instance.id,
            action="soft_delete",
            before_state=before_state,
            after_state=ResourcesSerializer(instance).data,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _build_access_payload(self, resource):
        # Resource access is explicit so the frontend can stop guessing whether a resource is
        # directly downloadable, opens as an external page, or is not yet wired to storage.
        storage_key = (resource.storage_key or "").strip()
        external_url = storage_key if storage_key.startswith(("http://", "https://")) else None
        if not storage_key:
            access_mode = "unavailable"
            detail = "This resource does not have a configured storage target yet."
        elif external_url and resource.kind == Resources.ResourceKind.PAGE:
            access_mode = "external_page"
            detail = None
        elif external_url and resource.kind == Resources.ResourceKind.FILE:
            access_mode = "external_file"
            detail = None
        else:
            access_mode = "managed_key"
            detail = "This deployment does not yet resolve managed storage keys into public download URLs."

        serializer = ResourceListSerializer(resource, context={"request": self.request})
        resource_data = serializer.data
        return {
            "resource_id": resource.id,
            "kind": resource.kind,
            "storage_status": resource_data["storage_status"],
            "access_mode": access_mode,
            "access_url": resource_data["access_url"],
            "download_url": resource_data["download_url"],
            "external_url": external_url,
            "file_name": resource_data["file_name"],
            "file_mime_type": resource.file_mime_type,
            "file_size": resource.file_size,
            "detail": detail,
        }

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def access(self, request, pk=None):
        resource = self.get_object()
        can_access, reason = self._user_can_access_resource(request.user, resource)
        if not can_access:
            return Response({"error": "Permission denied", "detail": reason}, status=status.HTTP_403_FORBIDDEN)

        payload = self._build_access_payload(resource)
        return Response(ResourceAccessSerializer(payload).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def download(self, request, pk=None):
        resource = self.get_object()
        can_access, reason = self._user_can_access_resource(request.user, resource)
        if not can_access:
            return Response({"error": "Permission denied", "detail": reason}, status=status.HTTP_403_FORBIDDEN)

        payload = self._build_access_payload(resource)
        external_url = payload["external_url"]
        if external_url and payload["access_mode"] in {"external_file", "external_page"}:
            return HttpResponseRedirect(external_url)

        return Response(
            {
                "detail": payload["detail"],
                "resource": ResourceAccessSerializer(payload).data,
            },
            status=status.HTTP_409_CONFLICT,
        )
    
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
            if ResourceAudience.objects.filter(resource=resource, role=role, track__isnull=True).exists():
                return Response(
                    {"error": "Role is already assigned to this resource"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ResourceAudience.objects.create(resource=resource, role=role)
            
            return Response({
                "message": f"Role '{role.role_name}' assigned to resource '{resource.name}'",
                "resource_id": resource.id,
                "resource_name": resource.name,
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
            resource_role = ResourceAudience.objects.get(resource=resource, role=role, track__isnull=True)
            role_name = role.role_name
            resource_role.delete()
            
            return Response({
                "message": f"Role '{role_name}' removed from resource '{resource.name}'"
            }, status=status.HTTP_200_OK)
            
        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ResourceAudience.DoesNotExist:
            return Response(
                {"error": "Role is not assigned to this resource"},
                status=status.HTTP_404_NOT_FOUND
            )


class ResourceTypeViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    queryset = ResourceType.objects.all().order_by("type_name")
    serializer_class = ResourceTypeSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
