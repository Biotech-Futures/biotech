from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.groups.models import GroupAutoNameUnavailable, GroupInterest, GroupMembership, Groups
from apps.groups.services import assign_mentor_to_group, sync_supervisor_memberships_for_student
from apps.users.models import AreasOfInterest, MentorProfile, StudentProfile, SupervisorProfile, User
from apps.users.serializers import (
    SupervisedGroupMemberChangeSerializer,
    SupervisedGroupSerializer,
    SupervisedGroupWriteSerializer,
    SupervisedInterestCatalogSerializer,
    SupervisedMentorSerializer,
)


def _require_supervisor(user):
    if not SupervisorProfile.objects.filter(user=user).exists():
        raise PermissionDenied("Supervisor access is required.")


def _member_payload(membership):
    person = membership.user
    return {
        "id": person.id,
        "first_name": person.first_name or "",
        "last_name": person.last_name or "",
        "email": person.email,
        "role": membership.membership_role or "student",
    }


def _group_payload(group):
    members = [
        _member_payload(membership)
        for membership in GroupMembership.objects.filter(group=group, left_at__isnull=True)
        .select_related("user")
        .order_by("membership_role", "user__first_name", "user__last_name", "user_id")
    ]
    interests = sorted(
        {
            description
            for description in GroupInterest.objects.filter(group=group).values_list(
                "interest__interest_desc", flat=True
            )
            if description
        },
        key=str.lower,
    )
    return {
        "id": group.id,
        "group_name": group.group_name,
        "members": members,
        "interests": interests,
    }


def _normalize_interest_descriptions(interests):
    if not interests:
        return []
    trimmed = [item.strip() for item in interests if str(item).strip()]
    return list(dict.fromkeys(trimmed))


def _resolve_interest_ids(interests):
    interest_ids = []
    for description in _normalize_interest_descriptions(interests):
        interest, _created = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description,
            defaults={"interest_desc": description},
        )
        interest_ids.append(interest.id)
    return interest_ids


def _sync_group_interests(group, descriptions):
    GroupInterest.objects.filter(group=group).delete()
    interest_ids = _resolve_interest_ids(descriptions)
    GroupInterest.objects.bulk_create(
        [GroupInterest(group=group, interest_id=interest_id) for interest_id in interest_ids]
    )


def _owned_groups(user):
    return Groups.objects.filter(
        deleted_at__isnull=True,
        groupmembership__user=user,
        groupmembership__left_at__isnull=True,
        groupmembership__membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
    ).distinct()


def _owned_group(user, group_id):
    group = _owned_groups(user).filter(pk=group_id).first()
    if group is None:
        raise PermissionDenied("This group is not on your roster.")
    return group


def _keep_supervisor_on_group(group, user):
    GroupMembership.objects.get_or_create(
        group=group,
        user=user,
        left_at=None,
        defaults={"membership_role": GroupMembership.MembershipRoleChoices.SUPERVISOR},
    )


def _owned_group_ids(user):
    return list(_owned_groups(user).values_list("id", flat=True))


def _restore_supervisor_on_groups(user, group_ids):
    for group in Groups.objects.filter(pk__in=group_ids, deleted_at__isnull=True):
        _keep_supervisor_on_group(group, user)


class SupervisedGroupsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(responses={200: SupervisedGroupSerializer(many=True)})
    def get(self, request):
        _require_supervisor(request.user)
        groups = _owned_groups(request.user).order_by("group_name", "id")
        return Response(SupervisedGroupSerializer([_group_payload(group) for group in groups], many=True).data)

    @extend_schema(request=SupervisedGroupWriteSerializer, responses={201: SupervisedGroupSerializer})
    @transaction.atomic
    def post(self, request):
        _require_supervisor(request.user)
        serializer = SupervisedGroupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            group = Groups.create_auto_named()
        except GroupAutoNameUnavailable as exc:
            raise ValidationError({"group_name": [str(exc)]}) from exc
        _keep_supervisor_on_group(group, request.user)
        if "interests" in request.data:
            _sync_group_interests(group, serializer.validated_data.get("interests") or [])
        return Response(SupervisedGroupSerializer(_group_payload(group)).data, status=status.HTTP_201_CREATED)


class SupervisedGroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(responses={200: SupervisedGroupSerializer})
    def get(self, request, pk):
        _require_supervisor(request.user)
        return Response(SupervisedGroupSerializer(_group_payload(_owned_group(request.user, pk))).data)

    @extend_schema(request=SupervisedGroupWriteSerializer, responses={200: SupervisedGroupSerializer})
    @transaction.atomic
    def patch(self, request, pk):
        _require_supervisor(request.user)
        group = _owned_group(request.user, pk)
        serializer = SupervisedGroupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "interests" not in request.data:
            raise ValidationError({"interests": ["Group names are assigned by the system. Update areas of interest instead."]})
        _sync_group_interests(group, serializer.validated_data.get("interests") or [])
        return Response(SupervisedGroupSerializer(_group_payload(group)).data)

    @transaction.atomic
    def delete(self, request, pk):
        _require_supervisor(request.user)
        group = _owned_group(request.user, pk)
        if group.deleted_at is None:
            group.deleted_at = timezone.now()
            group.save(update_fields=["deleted_at"])
        owned_ids = [group_id for group_id in _owned_group_ids(request.user) if group_id != group.id]
        student_ids = list(
            GroupMembership.objects.filter(
                group=group,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            ).values_list("user_id", flat=True)
        )
        for student_id in student_ids:
            sync_supervisor_memberships_for_student(student_id)
        _restore_supervisor_on_groups(request.user, owned_ids)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupervisedGroupMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(request=SupervisedGroupMemberChangeSerializer, responses={200: SupervisedGroupSerializer})
    @transaction.atomic
    def post(self, request, pk):
        _require_supervisor(request.user)
        group = _owned_group(request.user, pk)
        owned_ids = set(_owned_group_ids(request.user))
        serializer = SupervisedGroupMemberChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get("role") or "student"
        user_ids = serializer.validated_data["user_ids"]

        if role == "mentor":
            if len(user_ids) != 1:
                raise ValidationError({"user_ids": ["Assign one mentor at a time."]})
            mentor = User.objects.filter(pk=user_ids[0]).first()
            if mentor is None:
                raise PermissionDenied("One or more people are not available to assign.")
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                assign_mentor_to_group(group=group, mentor_user=mentor, replace_existing=True)
            except DjangoValidationError as exc:
                raise ValidationError({"user_ids": exc.messages}) from exc
            _keep_supervisor_on_group(group, request.user)
            return Response(SupervisedGroupSerializer(_group_payload(group)).data)

        profiles = list(
            StudentProfile.objects.filter(supervisor_id=request.user.id, user_id__in=user_ids)
        )
        found = {profile.user_id for profile in profiles}
        if [user_id for user_id in user_ids if user_id not in found]:
            raise PermissionDenied("One or more students are not on your roster.")

        now = timezone.now()
        vacated_group_ids = set(
            GroupMembership.objects.filter(
                user_id__in=user_ids,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )
            .exclude(group=group)
            .values_list("group_id", flat=True)
        )
        GroupMembership.objects.filter(
            user_id__in=user_ids,
            left_at__isnull=True,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        ).exclude(group=group).update(left_at=now)

        for user_id in user_ids:
            GroupMembership.objects.get_or_create(
                group=group,
                user_id=user_id,
                left_at=None,
                defaults={"membership_role": GroupMembership.MembershipRoleChoices.STUDENT},
            )
            sync_supervisor_memberships_for_student(user_id)
        _restore_supervisor_on_groups(request.user, owned_ids | vacated_group_ids | {group.id})
        return Response(SupervisedGroupSerializer(_group_payload(group)).data)

    @extend_schema(request=SupervisedGroupMemberChangeSerializer, responses={200: SupervisedGroupSerializer})
    @transaction.atomic
    def delete(self, request, pk):
        _require_supervisor(request.user)
        group = _owned_group(request.user, pk)
        owned_ids = set(_owned_group_ids(request.user))
        serializer = SupervisedGroupMemberChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data["user_ids"]
        now = timezone.now()
        memberships = list(
            GroupMembership.objects.filter(group=group, user_id__in=user_ids, left_at__isnull=True)
        )
        for membership in memberships:
            if (
                membership.user_id == request.user.id
                and membership.membership_role == GroupMembership.MembershipRoleChoices.SUPERVISOR
            ):
                raise ValidationError({"user_ids": ["You cannot remove yourself from the group."]})
            membership.left_at = now
            membership.save(update_fields=["left_at"])
            if membership.membership_role == GroupMembership.MembershipRoleChoices.STUDENT:
                sync_supervisor_memberships_for_student(membership.user_id)
        _restore_supervisor_on_groups(request.user, owned_ids | {group.id})
        return Response(SupervisedGroupSerializer(_group_payload(group)).data)


class SupervisedInterestCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(responses={200: SupervisedInterestCatalogSerializer})
    def get(self, request):
        _require_supervisor(request.user)
        interests = list(
            AreasOfInterest.objects.order_by("interest_desc").values_list("interest_desc", flat=True)
        )
        return Response(SupervisedInterestCatalogSerializer({"interests": interests}).data)


class SupervisedMentorsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(responses={200: SupervisedMentorSerializer(many=True)})
    def get(self, request):
        _require_supervisor(request.user)
        mentors = (
            MentorProfile.objects.select_related("user")
            .order_by("user__first_name", "user__last_name", "user_id")
        )
        payload = [
            {
                "id": mentor.user_id,
                "first_name": mentor.user.first_name or "",
                "last_name": mentor.user.last_name or "",
                "email": mentor.user.email,
            }
            for mentor in mentors
        ]
        return Response(SupervisedMentorSerializer(payload, many=True).data)
