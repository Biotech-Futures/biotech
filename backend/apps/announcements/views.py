from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.resources.models import RoleAssignmentHistory

from .models import Announcement
from .serializers import AnnouncementSerializer


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

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user

        if not user or not user.is_authenticated:
            return Announcement.objects.none()

        include_archived = str(self.request.query_params.get("include_archived", "")).lower() in {"1", "true", "yes"}
        if not include_archived:
            queryset = queryset.filter(archived_at__isnull=True)

        search_text = (self.request.query_params.get("q") or self.request.query_params.get("search") or "").strip()
        if search_text:
            queryset = queryset.filter(Q(title__icontains=search_text) | Q(body__icontains=search_text))

        visibility_scope = self.request.query_params.get("visibility_scope")
        if visibility_scope:
            queryset = queryset.filter(visibility_scope=visibility_scope)

        track_id = self.request.query_params.get("track_id")
        if track_id:
            queryset = queryset.filter(Q(track_id=track_id) | Q(audiences__track_id=track_id))

        if user.is_staff or user.is_superuser:
            # Staff should see the full management surface, but still through the same predictable
            # list contract and filters the SPA will rely on.
            return queryset.distinct().order_by("-published_at", "-id")

        now = timezone.now()
        role_ids = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).values_list("role_id", flat=True)

        audience_filter = Q(author_user=user) | Q(visibility_scope=Announcement.VisibilityScope.PUBLIC)
        if role_ids:
            audience_filter |= Q(audiences__role_id__in=role_ids)
        if user.track_id:
            audience_filter |= Q(track_id=user.track_id) | Q(audiences__track_id=user.track_id)

        return queryset.filter(audience_filter).distinct().order_by("-published_at", "-id")

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
