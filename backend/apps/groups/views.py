from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema
from .models import Groups, Countries, GroupMembership, Tracks
from .serializers import (
    CountrySerializer,
    GroupMembershipSerializer,
    TrackSerializer,
    GroupSerializer,
    BulkUserSerializer,
    BulkGroupCreateSerializer,
    MentorAssignmentSerializer,
)
from .services import (
    MEMBER_MEMBERSHIP_ROLE,
    MENTOR_MEMBERSHIP_ROLE,
    assign_mentor_to_group,
)
from apps.audit.services import log_audit_event
from apps.users.utils.admin_scope import can_admin_track, is_operational_admin


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Countries.objects.order_by("country_name")
    serializer_class = CountrySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminUser()]


class GroupMemberViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer

    def get_queryset(self):
        queryset = GroupMembership.objects.select_related("group", "user").order_by("id")
        raw = (self.request.query_params.get("include_inactive") or "").lower().strip()
        if raw == "true" and self.request.user.is_staff:
            return queryset
        return queryset.filter(left_at__isnull=True)

    def get_permissions(self):
        if self.action in ["list", "retrieve", "by_group"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='by-group/(?P<group_id>[^/.]+)')
    def by_group(self, request, group_id=None):
        """Custom action to get members by group ID"""
        members = self.get_queryset().filter(group_id=group_id)
        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if membership.left_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrackViewSet(viewsets.ModelViewSet):
    queryset = Tracks.objects.order_by("track_name", "id")
    serializer_class = TrackSerializer
    http_method_names = ['get', 'post', 'put', 'patch']
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['track_name', 'id']
    search_fields = ['track_name']

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        # Only restore and staff recovery views can see tombstoned groups.
        if self.action == "restore":
            return Groups.objects.order_by("group_name", "id")
        raw = (self.request.query_params.get('include_deleted') or '').lower().strip()
        if raw == 'true' and self.request.user.is_staff:
            return Groups.objects.order_by("group_name", "id")
        return Groups.objects.filter(deleted_at__isnull=True).order_by("group_name", "id")

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.deleted_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        group.deleted_at = timezone.now()
        group.save(update_fields=['deleted_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="restore")
    @transaction.atomic
    def restore(self, request, pk=None):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
        if group.deleted_at is None:
            return Response(GroupSerializer(group).data, status=status.HTTP_200_OK)
        # Restore must respect the active-only uniqueness constraint.
        if Groups.objects.filter(
            track=group.track,
            group_name=group.group_name,
            deleted_at__isnull=True,
        ).exclude(pk=group.pk).exists():
            raise ValidationError({
                "group_name": "An active group with this name already exists in this track."
            })

        before_state = GroupSerializer(group).data
        group.restore()
        group.refresh_from_db()
        log_audit_event(
            actor=request.user,
            entity_type="group",
            entity_id=group.id,
            action="restore",
            before_state=before_state,
            after_state=GroupSerializer(group).data,
        )
        return Response(GroupSerializer(group).data, status=status.HTTP_200_OK)

    def _ensure_admin_track_access(self, request, track_or_group):
        if not is_operational_admin(request.user):
            raise PermissionDenied("Operational admin access is required.")
        track = getattr(track_or_group, "track", track_or_group)
        if not can_admin_track(request.user, track):
            raise PermissionDenied("You do not have admin scope for this track.")

    @extend_schema(request=BulkGroupCreateSerializer, responses={201: GroupSerializer(many=True)})
    @action(detail=False, methods=['post'], url_path='bulk-create', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def bulk_create(self, request):
        serializer = BulkGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_groups = []
        for group_payload in serializer.validated_data["groups"]:
            track = group_payload["track"]
            self._ensure_admin_track_access(request, track)
            group = Groups.objects.create(
                group_name=group_payload["group_name"],
                track=track,
            )
            member_users = group_payload.get("member_user_ids") or []
            for member_user in member_users:
                GroupMembership.objects.get_or_create(
                    group=group,
                    user=member_user,
                    left_at=None,
                    defaults={"membership_role": MEMBER_MEMBERSHIP_ROLE},
                )

            mentor_user = group_payload.get("mentor_user_id")
            if mentor_user is not None:
                try:
                    assign_mentor_to_group(group=group, mentor_user=mentor_user, replace_existing=False)
                except DjangoValidationError as exc:
                    raise ValidationError({"mentor_user_id": exc.messages}) from exc

            created_groups.append(group)
            log_audit_event(
                actor=request.user,
                entity_type="group",
                entity_id=group.id,
                action="bulk_create",
                after_state=GroupSerializer(group).data,
            )

        return Response(GroupSerializer(created_groups, many=True).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=BulkUserSerializer, responses={200: GroupMembershipSerializer(many=True)})
    @action(detail=True, methods=['post'], url_path='add-members', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def add_members(self, request, pk=None):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
        serializer = BulkUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        memberships = []
        for user_id in serializer.validated_data["user_ids"]:
            membership, _ = GroupMembership.objects.get_or_create(
                group=group,
                user_id=user_id,
                left_at=None,
                defaults={"membership_role": MEMBER_MEMBERSHIP_ROLE},
            )
            memberships.append(membership)

        log_audit_event(
            actor=request.user,
            entity_type="group",
            entity_id=group.id,
            action="add_members",
            after_state={"member_user_ids": serializer.validated_data["user_ids"]},
        )
        return Response(GroupMembershipSerializer(memberships, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(request=BulkUserSerializer, responses={200: GroupMembershipSerializer(many=True)})
    @action(detail=True, methods=['post'], url_path='remove-members', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def remove_members(self, request, pk=None):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
        serializer = BulkUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_memberships = list(
            GroupMembership.objects.filter(
                group=group,
                user_id__in=serializer.validated_data["user_ids"],
                left_at__isnull=True,
            ).order_by("id")
        )
        now = timezone.now()
        for membership in active_memberships:
            membership.left_at = now
            membership.save(update_fields=["left_at"])

        log_audit_event(
            actor=request.user,
            entity_type="group",
            entity_id=group.id,
            action="remove_members",
            after_state={"member_user_ids": serializer.validated_data["user_ids"]},
        )
        return Response(GroupMembershipSerializer(active_memberships, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(request=MentorAssignmentSerializer, responses={200: GroupMembershipSerializer})
    @action(detail=True, methods=['post'], url_path='assign-mentor', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def assign_mentor(self, request, pk=None):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
        serializer = MentorAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = assign_mentor_to_group(
                group=group,
                mentor_user=serializer.validated_data["mentor_user_id"],
                replace_existing=False,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"mentor_user_id": exc.messages}) from exc

        membership = result["membership"]
        log_audit_event(
            actor=request.user,
            entity_type="group",
            entity_id=group.id,
            action="assign_mentor",
            after_state={"mentor_user_id": membership.user_id},
        )
        return Response(GroupMembershipSerializer(membership).data, status=status.HTTP_200_OK)

    @extend_schema(request=MentorAssignmentSerializer, responses={200: GroupMembershipSerializer})
    @action(detail=True, methods=['post'], url_path='replace-mentor', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def replace_mentor(self, request, pk=None):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
        serializer = MentorAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = assign_mentor_to_group(
                group=group,
                mentor_user=serializer.validated_data["mentor_user_id"],
                replace_existing=True,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"mentor_user_id": exc.messages}) from exc

        membership = result["membership"]
        log_audit_event(
            actor=request.user,
            entity_type="group",
            entity_id=group.id,
            action="replace_mentor",
            after_state={
                "mentor_user_id": membership.user_id,
                "replaced_mentor_user_ids": [item.user_id for item in result["replaced_memberships"]],
            },
        )
        return Response(GroupMembershipSerializer(membership).data, status=status.HTTP_200_OK)
