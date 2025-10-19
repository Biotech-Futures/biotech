from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, viewsets, generics, status
from .models import Events, EventInvite
from .serializers import EventSerializer, EventInviteCreateSerializers, EventInviteSerializers
from apps.users.models import User
from apps.resources.models import RoleAssignmentHistory
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    GET allowed for anyone (or only authenticated if you prefer).
    POST allowed only for staff/admin users.
    """
    def has_permission(self, request, view):
        if request.method == "POST":
            return bool(request.user and request.user.is_staff)
        return True  # change to: return bool(request.user and request.user.is_authenticated) if you want auth-only reads

class EventViewSet(mixins.ListModelMixin,
                   mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly] # This was blocking devs from testing POST requests

    def get_queryset(self):
        now = timezone.now()
        # Upcoming, not soft-deleted
        return (
            Events.objects
            .filter(deleted_flag=False, start_datetime__gte=now)
            .order_by("start_datetime")
        )

    def perform_create(self, serializer):
        # Attach creator if available; your model allows NULL host_user
        serializer.save(host_user=self.request.user if self.request.user.is_authenticated else None)

class IsNotStudent(permissions.BasePermission):
    def _get_active_role(self, user):
        """
        Get the user's current active role from RoleAssignmentHistory
        Returns the role_name (e.g., 'Mentor', 'Student', 'Supervisor', 'Admin')
        """
        if not user or not user.is_authenticated:
            return None
        
        now = timezone.now()
        
        # Get active role: valid_to is NULL (ongoing) or in the future
        active_role = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).select_related('role').first()
        
        if active_role and active_role.role:
            return active_role.role.role_name
        
        return None
    
    def has_permission(self, request, view):
        """
        Check if user has permission to access the endpoints
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Django staff/superuser always have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Get user's active role
        role_name = self._get_active_role(request.user)
        
        if not role_name:
            return False  # No active role = no access

        # Normalize role name for comparison (case-insensitive)
        role_name = role_name.lower()

        if role_name == 'mentor':
            return True

        if role_name == 'supervisor':
            return True
        
        if role_name == "administrator":
            return True

        # Students have no access
        return False

class EventInviteCreateView(APIView):
    # permission_classes = [permissions.AllowAny]
    permission_classes = [IsNotStudent]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        event_id = kwargs.get("id")
        event = get_object_or_404(Events, pk=event_id)

        user_id = kwargs.get("uid")
        user = get_object_or_404(User, pk=user_id)

        ei = EventInvite.objects.create(
            event=event,
            user=user,
            sent_datetime=timezone.now()
        )
        return Response(EventInviteCreateSerializers(ei).data, status=status.HTTP_200_OK)
    

class EventPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100

class EventInviteListHTMLView(generics.ListAPIView):
    # queryset = EventInvite.objects.all()
    serializer_class = EventInviteSerializers
    # permission_classes = [permissions.AllowAny]
    permission_classes = [IsNotStudent]
    pagination_class = EventPagePagination

    def get_queryset(self):
        event_id = self.kwargs.get("id")
        event = get_object_or_404(Events, pk=event_id)

        return (
            EventInvite.objects.select_related("event").filter(event=event).order_by("id")
        )
    
class EventInviteListMeHTMLView(generics.ListAPIView):
    serializer_class = EventInviteSerializers
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EventPagePagination

    def get_queryset(self):
        user = self.request.user

        return (
            EventInvite.objects.select_related("event").filter(user=user).order_by("id")
        )
