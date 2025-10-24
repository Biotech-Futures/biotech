from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, viewsets, generics, status
from rest_framework.decorators import action
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


class IsAdminOrEventHost(permissions.BasePermission):
    """
    Permission class: Allow admins or event creators (host_user) to modify/delete events.
    """
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user and request.user.is_staff:
            return True
        # Event host can modify their own events
        if request.user and obj.host_user == request.user:
            return True
        return False


class EventViewSet(mixins.ListModelMixin,
                   mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        """
        Set permissions based on action:
        - List/Retrieve: Public (IsAdminOrReadOnly)
        - Create: Admin only
        - Update/Delete: Admin or event host
        - Registration actions: Authenticated users
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminOrEventHost()]
        elif self.action in ['register', 'cancel', 'my_registration']:
            return [permissions.IsAuthenticated()]
        elif self.action == 'attendees':
            return [IsAdminOrEventHost()]
        return [IsAdminOrReadOnly()]

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

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete event: Set deleted_flag=True and deleted_datetime=now()
        """
        event = self.get_object()
        event.deleted_flag = True
        event.deleted_datetime = timezone.now()
        event.save(update_fields=['deleted_flag', 'deleted_datetime'])
        return Response(
            {"message": f"Event '{event.event_name}' has been deleted."},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'], url_path='register')
    def register(self, request, pk=None):
        """
        Register current user for event.
        Creates or updates EventInvite with rsvp_status=True.
        POST /events/v1/{id}/register/
        """
        event = self.get_object()
        user = request.user

        # Get or create EventInvite
        invite, created = EventInvite.objects.get_or_create(
            event=event,
            user=user,
            defaults={'sent_datetime': timezone.now(), 'rsvp_status': True}
        )

        # If invite already existed, update rsvp_status
        if not created:
            if invite.rsvp_status:
                return Response(
                    {
                        "message": "You are already registered for this event.",
                        "invite": EventInviteSerializers(invite).data
                    },
                    status=status.HTTP_200_OK
                )
            invite.rsvp_status = True
            invite.save(update_fields=['rsvp_status'])

        return Response(
            {
                "message": f"Successfully registered for '{event.event_name}'",
                "event": EventSerializer(event).data,
                "invite": EventInviteSerializers(invite).data
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        Cancel registration for event.
        Sets rsvp_status=False and attendance_status=False.
        POST /events/v1/{id}/cancel/
        """
        event = self.get_object()
        user = request.user

        try:
            invite = EventInvite.objects.get(event=event, user=user)
        except EventInvite.DoesNotExist:
            return Response(
                {"error": "You are not registered for this event."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not invite.rsvp_status:
            return Response(
                {"message": "You are already not registered for this event."},
                status=status.HTTP_200_OK
            )

        invite.rsvp_status = False
        invite.attendance_status = False
        invite.save(update_fields=['rsvp_status', 'attendance_status'])

        return Response(
            {
                "message": f"Registration cancelled for '{event.event_name}'",
                "invite": EventInviteSerializers(invite).data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='my-registration')
    def my_registration(self, request, pk=None):
        """
        Check current user's registration status for this event.
        GET /events/v1/{id}/my-registration/
        """
        event = self.get_object()
        user = request.user

        try:
            invite = EventInvite.objects.get(event=event, user=user)
            return Response(
                {
                    "registered": invite.rsvp_status,
                    "invite": EventInviteSerializers(invite).data
                },
                status=status.HTTP_200_OK
            )
        except EventInvite.DoesNotExist:
            return Response(
                {
                    "registered": False,
                    "invite": None
                },
                status=status.HTTP_200_OK
            )

    @action(detail=True, methods=['get'], url_path='attendees')
    def attendees(self, request, pk=None):
        """
        Get list of attendees for this event (admin/host only).
        Supports filtering: ?rsvp_status=true&attendance_status=true
        GET /events/v1/{id}/attendees/
        """
        event = self.get_object()

        # Filter invites for this event
        invites = EventInvite.objects.filter(event=event).select_related('user')

        # Apply query param filters
        rsvp_filter = request.query_params.get('rsvp_status')
        attendance_filter = request.query_params.get('attendance_status')

        if rsvp_filter is not None:
            rsvp_bool = rsvp_filter.lower() == 'true'
            invites = invites.filter(rsvp_status=rsvp_bool)

        if attendance_filter is not None:
            attendance_bool = attendance_filter.lower() == 'true'
            invites = invites.filter(attendance_status=attendance_bool)

        serializer = EventInviteSerializers(invites, many=True)

        return Response(
            {
                "event_id": event.id,
                "event_name": event.event_name,
                "total_invites": invites.count(),
                "attendees": serializer.data
            },
            status=status.HTTP_200_OK
        )


class MarkAttendanceView(APIView):
    """
    Mark attendance for an event invite.
    PATCH /events/v1/invites/{invite_id}/mark-attendance/
    Permission: Admin or event host only
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, invite_id):
        try:
            invite = EventInvite.objects.select_related('event').get(pk=invite_id)
        except EventInvite.DoesNotExist:
            return Response(
                {"error": "Event invite not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permission: Must be admin or event host
        event = invite.event
        if not request.user.is_staff and event.host_user != request.user:
            return Response(
                {"error": "You do not have permission to mark attendance for this event."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get attendance_status from request
        attendance_status = request.data.get('attendance_status')

        if attendance_status is None:
            return Response(
                {"error": "attendance_status is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate: Can only mark attendance if user RSVP'd
        if attendance_status and not invite.rsvp_status:
            return Response(
                {
                    "error": "Cannot mark attendance as true for users who haven't RSVP'd. "
                            "RSVP status must be true first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update attendance
        invite.attendance_status = bool(attendance_status)
        invite.save(update_fields=['attendance_status'])

        return Response(
            {
                "message": "Attendance updated successfully.",
                "invite": EventInviteSerializers(invite).data
            },
            status=status.HTTP_200_OK
        )


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
