from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from .models import Events, EventInvite
from .serializers import EventSerializer, EventInviteSerializer
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

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


def is_mentor_or_above(user):
    return user.is_staff or user.groups.filter(name='Mentors').exists()

class EventInviteViewSet(viewsets.GenericViewSet):
    queryset = EventInvite.objects.all().order_by('-sent_datetime')
    serializer_class = EventInviteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    """
    PATCH /api/v1/events/{event_id}/rsvp/
    Update RSVP (accept/decline) for the logged-in user
    """

    def rsvp_event(self, request, event_id: int):
        event = get_object_or_404(Events, pk=event_id, deleted_flag=False)
        invite = EventInvite.objects.filter(event=event, user=request.user).first()
        if not invite:
            raise serializers.ValidationError(
                {"detail": "User is not invited."}
            )
        rsvp = request.data.get("rsvp_status", None)
        if rsvp is None:
            raise serializers.ValidationError(
                {"rsvp_status": "true/false is required."}
            )
        
        if invite.rsvp_status is False:
            invite.attendance_status = False
        
        invite.save()
        return Response(EventInviteSerializer(invite).data, status=200)
    
    """
    PATCH /api/v1/events/{event_id}/attendance/
    Update attendance status (mark who attended)
    """
    
    def attendance_for_event(self, request, event_id: int):
        if not is_mentor_or_above(request.user):
            return Response({"detail": "User does not have permission to mark attendance"}, status=403)

        event = get_object_or_404(Events, pk=event_id, deleted_flag=False)

        attended = request.data.get("attendance_status", None)
        if attended is None:
            raise serializers.ValidationError({"attendance_status": "true/false is required."})

        target_user_id = request.data.get("user_id") or request.user.id
        invite = EventInvite.objects.filter(event=event, user_id=target_user_id).first()
        if not invite:
            raise serializers.ValidationError({"detail": "Invite not found for user/event."})

        # if bool(attended) and not invite.rsvp_status:
        #     raise serializers.ValidationError({"attendance_status": "Cannot mark attendance unless RSVP is True."})

        # leaving this commented for now, need to confirm if RSVP is required for attendance marking

        invite.attendance_status = bool(attended)
        invite.save()
        return Response(EventInviteSerializer(invite).data, status=200)
    
    """
    GET /api/v1/events/{event_id}/attendees/
    Get attendance summary (accepted, rejected, pending, attended)
    """
    
    def attendees_for_event(self, request, event_id: int):
        event = get_object_or_404(Events, pk=event_id, deleted_flag=False)
        qs = EventInvite.objects.filter(event=event)

        accepted = qs.filter(rsvp_status=True).count()
        rejected = qs.filter(rsvp_status=False).count()
        # pending  = qs.filter(rsvp_status__isnull=True).count()  
        # at the moment can't implement pending as rsvp_status defaults to False
        attended = qs.filter(attendance_status=True).count()

        return Response({
            "event_id": event.id,
            "accepted": accepted,
            "rejected": rejected,
            # "pending": pending,
            "attended": attended,
        }, status=200)




        
