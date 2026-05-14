from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from apps.audit.services import log_audit_event

from .models import Announcement
from .serializers import AnnouncementListSerializer, AnnouncementSerializer
from .services import visible_announcements_queryset


class AnnouncementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Announcement.objects.select_related("author_user", "track").prefetch_related("audiences__role", "audiences__track").all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Listing returns body truncated to 4 KB; detail returns the full
        # body. Prevents one announcement with an embedded base64 image
        # from inflating every list response.
        if self.action == "list":
            return AnnouncementListSerializer
        return AnnouncementSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Admins keep visibility into archived rows so they can audit and
        # restore — non-admin filtering happens inside the service.
        qs = visible_announcements_queryset(self.request.user, include_archived=True)
        return qs.select_related("author_user", "track").prefetch_related(
            "audiences__role", "audiences__track"
        ).order_by("-published_at")

    def perform_create(self, serializer):
        announcement = serializer.save(author_user=self.request.user)
        log_audit_event(
            actor=self.request.user,
            entity_type="announcement",
            entity_id=announcement.id,
            action="create",
            after_state=AnnouncementSerializer(announcement).data,
        )

    def perform_update(self, serializer):
        before_state = AnnouncementSerializer(self.get_object()).data
        announcement = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="announcement",
            entity_id=announcement.id,
            action="update",
            before_state=before_state,
            after_state=AnnouncementSerializer(announcement).data,
        )

    def destroy(self, request, *args, **kwargs):
        announcement = self.get_object()
        before_state = AnnouncementSerializer(announcement).data
        announcement.archived_at = timezone.now()
        announcement.save(update_fields=["archived_at"])
        log_audit_event(
            actor=request.user,
            entity_type="announcement",
            entity_id=announcement.id,
            action="archive",
            before_state=before_state,
            after_state=AnnouncementSerializer(announcement).data,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
