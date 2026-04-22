from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import EventRsvp, EventTargetGroup, Events
from apps.groups.models import GroupMembership
from apps.tasks.models import Milestone, Tasks

from .serializers import NextEventSerializer, ProgressSnapshotSerializer


class ProgressSnapshotView(APIView):
    """
    GET /dashboard/v1/progress/

    Returns a progress snapshot for the authenticated user.
    - Students: aggregates tasks/milestones across their active groups.
    - Mentors/supervisors/admins: supports an optional ?group_id= filter.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='group_id',
                description='Limit snapshot to a specific group (optional).',
                required=False,
                type=int,
            )
        ],
        responses={200: ProgressSnapshotSerializer},
    )
    def get(self, request):
        user = request.user
        group_id_param = request.query_params.get('group_id')

        if group_id_param:
            group_ids = [group_id_param]
        else:
            group_ids = list(
                GroupMembership.objects.filter(user=user, left_at__isnull=True)
                .values_list('group_id', flat=True)
            )

        empty_scope = {
            'type': 'user',
            'user_id': user.id,
            'group_id': int(group_id_param) if group_id_param else None,
            'track_id': user.track_id,
        }

        if not group_ids:
            return Response({
                'completion_rate': 0,
                'completed_tasks': 0,
                'total_tasks': 0,
                'current_stage': None,
                'next_milestone': None,
                'scope': empty_scope,
                'updated_at': timezone.now(),
            })

        milestones = Milestone.objects.filter(
            group_id__in=group_ids,
            deleted_flag=False,
        ).order_by('sort_order', 'due_date', 'id')

        milestone_ids = list(milestones.values_list('id', flat=True))

        tasks = Tasks.objects.filter(
            milestone_id__in=milestone_ids,
            deleted_flag=False,
        )
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(completed=True).count()
        completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks else 0

        # Current stage = first incomplete milestone name (or 'Complete')
        current_milestone = milestones.filter(completed=False).first()
        current_stage = current_milestone.milestone_name if current_milestone else 'Complete'

        # Next milestone = first incomplete milestone that has a due date set
        next_ms = milestones.filter(completed=False, due_date__isnull=False).first()
        next_milestone_data = None
        if next_ms:
            next_milestone_data = {
                'id': next_ms.id,
                'name': next_ms.milestone_name,
                'due_date': next_ms.due_date,
            }

        scope_group_id = int(group_ids[0]) if len(group_ids) == 1 else None

        return Response({
            'completion_rate': completion_rate,
            'completed_tasks': completed_tasks,
            'total_tasks': total_tasks,
            'current_stage': current_stage,
            'next_milestone': next_milestone_data,
            'scope': {
                'type': 'user',
                'user_id': user.id,
                'group_id': scope_group_id,
                'track_id': user.track_id,
            },
            'updated_at': timezone.now(),
        })


class NextEventView(APIView):
    """
    GET /dashboard/v1/next-event/

    Returns the single next upcoming event most relevant to the authenticated user.
    Relevance is determined by:
      - Events targeting a group the user belongs to (EventTargetGroup)
      - Events on the user's track (Events.track)
      - Events the user has an RSVP record for

    Returns HTTP 204 if no relevant upcoming event is found.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: NextEventSerializer, 204: None},
    )
    def get(self, request):
        user = request.user
        now = timezone.now()

        base_qs = Events.objects.filter(
            deleted_flag=False,
            ends_datetime__gte=now,
        ).order_by('start_datetime')

        # Admins see the next platform-wide event
        if user.is_staff:
            event = base_qs.first()
            if event is None:
                return Response(None, status=status.HTTP_204_NO_CONTENT)
            return self._build_response(event, user)

        filter_conditions = []

        # Events that target a group the user is active in
        user_group_ids = list(
            GroupMembership.objects.filter(user=user, left_at__isnull=True)
            .values_list('group_id', flat=True)
        )
        if user_group_ids:
            group_event_ids = EventTargetGroup.objects.filter(
                group_id__in=user_group_ids
            ).values_list('event_id', flat=True)
            filter_conditions.append(Q(id__in=group_event_ids))

        # Events on the user's assigned track
        if user.track_id:
            filter_conditions.append(Q(track_id=user.track_id))

        # Events the user has an RSVP for
        rsvp_event_ids = EventRsvp.objects.filter(user=user).values_list('event_id', flat=True)
        if rsvp_event_ids:
            filter_conditions.append(Q(id__in=rsvp_event_ids))

        if not filter_conditions:
            return Response(None, status=status.HTTP_204_NO_CONTENT)

        combined = filter_conditions[0]
        for f in filter_conditions[1:]:
            combined |= f

        event = base_qs.filter(combined).first()
        if event is None:
            return Response(None, status=status.HTTP_204_NO_CONTENT)

        return self._build_response(event, user)

    def _build_response(self, event, user):
        rsvp = EventRsvp.objects.filter(event=event, user=user).first()
        rsvp_status = rsvp.rsvp_status if rsvp else 'pending'

        first_target_group = EventTargetGroup.objects.filter(event=event).first()
        group_id = first_target_group.group_id if first_target_group else None

        serializer = NextEventSerializer(
            event,
            context={'rsvp_status': rsvp_status, 'group_id': group_id},
        )
        return Response(serializer.data)
