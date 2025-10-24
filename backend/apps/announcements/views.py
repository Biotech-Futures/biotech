from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Announcement
from .serializers import (
    AnnouncementListSerializer,
    AnnouncementDetailSerializer,
    AnnouncementCreateUpdateSerializer
)
from apps.resources.models import RoleAssignmentHistory


class IsAdminOrAuthor(permissions.BasePermission):
    """
    Permission class: Allow admins or announcement authors to modify/delete announcements.
    All authenticated users can read.
    """
    def has_permission(self, request, view):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Write permissions for admins only
        return request.user and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Admin has full access
        if request.user and request.user.is_staff:
            return True

        # Author can modify their own announcements
        if request.user and obj.author == request.user:
            return True

        return False


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Announcement CRUD operations.

    Endpoints:
    - GET    /announcements/v1/          -> list (filtered by user's role)
    - POST   /announcements/v1/          -> create (admin only)
    - GET    /announcements/v1/{id}/     -> retrieve
    - PATCH  /announcements/v1/{id}/     -> update (admin or author)
    - DELETE /announcements/v1/{id}/     -> delete (admin or author)

    Filtering:
    - Automatically filters by audience based on user's role
    - Admins can override with ?audience=all query param
    - Search: ?search=keyword (searches title, summary, author name)
    """
    permission_classes = [IsAdminOrAuthor]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return AnnouncementListSerializer
        elif self.action == 'retrieve':
            return AnnouncementDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AnnouncementCreateUpdateSerializer
        return AnnouncementListSerializer

    def get_queryset(self):
        """
        Filter announcements based on user's role.
        Returns non-deleted announcements ordered by pinned status and date.
        """
        user = self.request.user
        queryset = Announcement.objects.filter(deleted_flag=False)

        # Get user's active role
        user_role = self._get_user_role(user)

        # Apply audience filtering
        # Admin override: can see all announcements if ?audience=all
        if user.is_staff:
            audience_override = self.request.query_params.get('audience')
            if audience_override == 'all':
                pass  # No filtering
            elif audience_override:
                queryset = queryset.filter(Q(audience='all') | Q(audience=audience_override))
            else:
                queryset = queryset.filter(Q(audience='all') | Q(audience='admin'))
        elif user_role:
            # Regular users see: 'all' + their specific role
            queryset = queryset.filter(Q(audience='all') | Q(audience=user_role))
        else:
            # No role = only see 'all' announcements
            queryset = queryset.filter(audience='all')

        # Apply search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(summary__icontains=search) |
                Q(author__first_name__icontains=search) |
                Q(author__last_name__icontains=search) |
                Q(author__email__icontains=search)
            )

        # Order by: pinned first, then newest
        return queryset.select_related('author').order_by('-is_pinned', '-created_datetime')

    def _get_user_role(self, user):
        """
        Get user's current active role from RoleAssignmentHistory.
        Returns: 'student', 'mentor', 'supervisor', 'admin', or None
        """
        if not user or not user.is_authenticated:
            return None

        now = timezone.now()

        # Get active role
        active_role = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).select_related('role').first()

        if active_role and active_role.role:
            role_name = active_role.role.role_name.lower()
            # Map role names to audience choices
            if 'student' in role_name:
                return 'student'
            elif 'mentor' in role_name:
                return 'mentor'
            elif 'supervisor' in role_name:
                return 'supervisor'
            elif 'admin' in role_name:
                return 'admin'

        return None

    def perform_create(self, serializer):
        """
        Set the author to the current user when creating an announcement.
        """
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete announcement.
        """
        announcement = self.get_object()
        announcement.deleted_flag = True
        announcement.deleted_datetime = timezone.now()
        announcement.save(update_fields=['deleted_flag', 'deleted_datetime'])

        return Response(
            {"message": f"Announcement '{announcement.title}' has been deleted."},
            status=status.HTTP_204_NO_CONTENT
        )
