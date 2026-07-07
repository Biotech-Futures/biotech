from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.resources.models import RoleAssignmentHistory

from apps.groups.models import GroupMembership

from .models import Announcement
from .serializers import AnnouncementListSerializer, AnnouncementSerializer


class AnnouncementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Announcement.objects.select_related("author_user").prefetch_related("audiences__role", "audiences__group").all()
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
        queryset = self.queryset
        user = self.request.user

        if not user or not user.is_authenticated:
            return Announcement.objects.none()

        if user.is_staff or user.is_superuser:
            return queryset.order_by("-published_at")

        now = timezone.now()
        role_ids = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).values_list("role_id", flat=True)

        # The admin API writes "global" for org-wide announcements; treat it as public.
        audience_filter = Q(author_user=user) | Q(
            visibility_scope__in=[
                Announcement.VisibilityScope.PUBLIC,
                Announcement.VisibilityScope.GLOBAL,
            ]
        )
        if role_ids:
            audience_filter |= Q(audiences__role_id__in=role_ids)

        # Group-targeted announcements: visible to active members of the
        # targeted group(s).
        group_ids = list(
            GroupMembership.objects.filter(user=user, left_at__isnull=True)
            .values_list("group_id", flat=True)
        )
        if group_ids:
            audience_filter |= Q(audiences__group_id__in=group_ids)

        return queryset.filter(Q(archived_at__isnull=True), audience_filter).distinct().order_by("-published_at")

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
