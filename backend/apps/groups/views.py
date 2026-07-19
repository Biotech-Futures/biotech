from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema
from .models import GroupAutoNameUnavailable, Groups, Countries, GroupMembership, group_name_sort_key
from .serializers import (
    CountrySerializer,
    GroupMembershipSerializer,
    GroupSerializer,
    BulkUserSerializer,
    BulkGroupCreateSerializer,
    MentorAssignmentSerializer,
)
from .services import (
    MEMBER_MEMBERSHIP_ROLE,
    assign_mentor_to_group,
    sync_supervisor_memberships_for_student,
)
from apps.audit.services import log_audit_event
from apps.common.rbac import is_admin


class IsOperationalAdminPermission(BasePermission):
    def has_permission(self, request, view):
        return is_admin(getattr(request, "user", None))


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Countries.objects.order_by("country_name")
    serializer_class = CountrySerializer

    def get_permissions(self):
        # ``list``/``retrieve`` were ``AllowAny`` historically; aligned with
        # the global ``IsAuthenticated`` default — see CONSOLIDATED issues
        # list 1.2. There is no documented reason to expose the country
        # catalogue pre-login.
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsOperationalAdminPermission()]


class GroupMemberViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer

    def get_queryset(self):
        queryset = GroupMembership.objects.select_related("group", "user").order_by("id")
        raw = (self.request.query_params.get("include_inactive") or "").lower().strip()
        if raw == "true" and is_admin(self.request.user):
            return queryset
        return queryset.filter(left_at__isnull=True)

    def get_permissions(self):
        if self.action in ["list", "retrieve", "by_group"]:
            return [IsAuthenticated()]
        return [IsOperationalAdminPermission()]

    def _ensure_admin_track_access(self, request, group):
        if not is_admin(request.user):
            raise PermissionDenied("Admin access is required.")

    @action(detail=False, methods=['get'], url_path='by-group/(?P<group_id>[^/.]+)')
    def by_group(self, request, group_id=None):
        """Custom action to get members by group ID"""
        members = self.get_queryset().filter(group_id=group_id)
        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        self._ensure_admin_track_access(request, membership.group)
        if membership.left_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        if membership.membership_role == GroupMembership.MembershipRoleChoices.STUDENT:
            sync_supervisor_memberships_for_student(membership.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        group = serializer.validated_data["group"]
        self._ensure_admin_track_access(self.request, group)
        membership = serializer.save()
        if membership.membership_role == GroupMembership.MembershipRoleChoices.STUDENT:
            sync_supervisor_memberships_for_student(membership.user_id)

    def perform_update(self, serializer):
        group = serializer.validated_data.get("group", serializer.instance.group)
        self._ensure_admin_track_access(self.request, group)
        membership = serializer.save()
        if membership.membership_role == GroupMembership.MembershipRoleChoices.STUDENT:
            sync_supervisor_memberships_for_student(membership.user_id)


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        # Only restore and operational-admin recovery views can see tombstoned groups.
        include_deleted = (self.request.query_params.get('include_deleted') or '').lower().strip() == 'true'
        if self.action == "restore":
            queryset = Groups.objects.all()
        elif include_deleted and is_admin(self.request.user):
            queryset = Groups.objects.all()
        else:
            queryset = Groups.objects.filter(deleted_at__isnull=True)

        mine = (self.request.query_params.get('mine') or '').lower().strip() == 'true'
        if mine and self.request.user.is_authenticated:
            # Active memberships only — a user who has left the group should
            # not see it in their "my groups" feed.
            queryset = queryset.filter(
                groupmembership__user=self.request.user,
                groupmembership__left_at__isnull=True,
            ).distinct()

        # Order on the padded key: raw group_name would sort "BTF10" before "BTF9".
        return queryset.annotate(group_name_key=group_name_sort_key()).order_by("group_name_key", "id")

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsOperationalAdminPermission()]

    def perform_create(self, serializer):
        self._ensure_admin_track_access(self.request, None)
        if (serializer.validated_data.get("group_name") or "").strip():
            group = serializer.save()
        else:
            try:
                group = Groups.create_auto_named()
            except GroupAutoNameUnavailable as exc:
                raise ValidationError({"group_name": [str(exc)]}) from exc
            # Point the serializer at the real row so the response carries the auto name.
            serializer.instance = group
        log_audit_event(
            actor=self.request.user,
            entity_type="group",
            entity_id=group.id,
            action="create",
            after_state=GroupSerializer(group).data,
        )

    def perform_update(self, serializer):
        group = serializer.instance
        self._ensure_admin_track_access(self.request, group)
        before_state = GroupSerializer(group).data
        group = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="group",
            entity_id=group.id,
            action="update",
            before_state=before_state,
            after_state=GroupSerializer(group).data,
        )

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        self._ensure_admin_track_access(request, group)
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
            group_name=group.group_name,
            deleted_at__isnull=True,
        ).exclude(pk=group.pk).exists():
            raise ValidationError({
                "group_name": "An active group with this name already exists."
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
        if not is_admin(request.user):
            raise PermissionDenied("Admin access is required.")

    @extend_schema(request=BulkGroupCreateSerializer, responses={201: GroupSerializer(many=True)})
    @action(detail=False, methods=['post'], url_path='bulk-create', permission_classes=[IsAuthenticated])
    @transaction.atomic
    def bulk_create(self, request):
        serializer = BulkGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_groups = []
        for group_payload in serializer.validated_data["groups"]:
            self._ensure_admin_track_access(request, None)
            requested_name = (group_payload.get("group_name") or "").strip()
            if requested_name:
                taken_error = ValidationError({
                    "group_name": [f'An active group named "{requested_name}" already exists.']
                })
                if Groups.objects.filter(
                    group_name=requested_name, deleted_at__isnull=True,
                ).exists():
                    raise taken_error
                try:
                    with transaction.atomic():
                        group = Groups.objects.create(group_name=requested_name)
                except IntegrityError as exc:
                    raise taken_error from exc
            else:
                try:
                    group = Groups.create_auto_named()
                except GroupAutoNameUnavailable as exc:
                    raise ValidationError({"group_name": [str(exc)]}) from exc
            member_users = group_payload.get("member_user_ids") or []
            for member_user in member_users:
                GroupMembership.objects.get_or_create(
                    group=group,
                    user=member_user,
                    left_at=None,
                    defaults={"membership_role": MEMBER_MEMBERSHIP_ROLE},
                )
                sync_supervisor_memberships_for_student(member_user.id)

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
            sync_supervisor_memberships_for_student(user_id)

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

        for membership in active_memberships:
            if membership.membership_role == GroupMembership.MembershipRoleChoices.STUDENT:
                sync_supervisor_memberships_for_student(membership.user_id)

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
