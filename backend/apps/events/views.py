from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from .models import Events
from .serializers import EventSerializer

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
