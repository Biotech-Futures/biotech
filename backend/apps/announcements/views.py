from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.groups.models.group_members import GroupMembership
from apps.resources.models import RoleAssignmentHistory
from .models import Announcement
from .serializers import AnnouncementSerializer


def get_active_role(user):
    """Returns the user's current active role name, or None."""
    now = timezone.now()
    active = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related('role').first()
    return active.role if active else None


class IsMentor(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        role = get_active_role(request.user)
        return role is not None and role.slug.lower() == 'mentor'


class IsAdministrator(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        role = get_active_role(request.user)
        return role is not None and role.slug.lower() == 'administrator'


class IsMentorOrAdministrator(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        role = get_active_role(request.user)
        if not role:
            return False
        return role.slug.lower() in ('mentor', 'administrator')


class AnnouncementCreateView(generics.CreateAPIView):
    serializer_class = AnnouncementSerializer
    permission_classes = [IsMentorOrAdministrator]

    def perform_create(self, serializer):
        role = get_active_role(self.request.user)
        role_name = role.slug.lower() if role else ''

        # Mentors must target a group
        if role_name == 'mentor' and not serializer.validated_data.get('group'):
            raise ValidationError({'group': 'Mentors must specify a group.'})

        serializer.save(created_by=self.request.user)


class AnnouncementListView(generics.ListAPIView):
    """Returns active announcements visible to the requesting user."""
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        now = timezone.now()
        user = self.request.user

        user_group_ids = GroupMembership.objects.filter(
            user=user
        ).values_list('group_id', flat=True)

        user_role = get_active_role(user)

        return Announcement.objects.filter(
            deleted_flag=False,
            start_date__lte=now,
            end_date__gte=now,
        ).filter(
            Q(group_id__in=user_group_ids) |          # targeted at user's group
            Q(target_role=user_role) |                 # targeted at user's role
            Q(group__isnull=True, target_role__isnull=True)  # targeted at everyone
        ).order_by('-created_at')


class AnnouncementDeleteView(APIView):
    """Soft delete — only the creator can delete their own announcement."""
    permission_classes = [IsMentorOrAdministrator]

    def delete(self, request, pk):
        try:
            announcement = Announcement.objects.get(pk=pk, deleted_flag=False)
        except Announcement.DoesNotExist:
            return Response({'detail': 'Announcement not found.'}, status=status.HTTP_404_NOT_FOUND)

        if announcement.created_by != request.user:
            return Response({'detail': 'You can only delete your own announcements.'}, status=status.HTTP_403_FORBIDDEN)

        announcement.deleted_flag = True
        announcement.deleted_datetime = timezone.now()
        announcement.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
