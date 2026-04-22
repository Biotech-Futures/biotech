"""
Dashboard API views — new dedicated endpoints requested in DASHBOARD_API_REQUIREMENTS.pdf.

#1  GET /dashboard/v1/progress/    — Progress Snapshot
#2  GET /dashboard/v1/next-event/  — Personalized Next Event
"""
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

    Why a dedicated endpoint instead of enhancing existing task/milestone APIs:
    The existing APIs return flat lists that the frontend has to aggregate itself.
    Role-aware progress (student vs mentor) cannot be expressed through a simple
    filter on the task list, and the frontend was approximating completion rate
    by guessing from milestones because Tasks had no `completed` field.

    Logic:
    - Infers the user's groups from active GroupMembership rows unless ?group_id= is given.
    - Loads all non-deleted milestones for those groups, ordered by sort_order then due_date.
    - Counts total and completed tasks across those milestones.
    - Reports the first incomplete milestone as the current stage and as the next milestone.
    - Returns HTTP 200 with zeroed counts if the user has no group memberships.

    Supported query params:
      ?group_id=<int>  — Limit the snapshot to a single group (useful for mentors/admins).
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
            # Derive groups from the user's active memberships so the endpoint is
            # role-aware without needing an explicit role parameter.
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

        # sort_order is the primary sequence; due_date and id are tie-breakers so the
        # result is stable even when sort_order values are equal or unset.
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
        # Guard against division by zero for groups that have milestones but no tasks yet.
        completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks else 0

        # current_stage is the name of the first milestone that still has work to do.
        # "Complete" signals that every milestone in scope is marked done.
        current_milestone = milestones.filter(completed=False).first()
        current_stage = current_milestone.milestone_name if current_milestone else 'Complete'

        # next_milestone is the earliest incomplete milestone that has a due_date set.
        # Milestones without a due_date are excluded so the frontend always gets a
        # displayable date or null rather than an empty object.
        next_ms = milestones.filter(completed=False, due_date__isnull=False).first()
        next_milestone_data = None
        if next_ms:
            next_milestone_data = {
                'id': next_ms.id,
                'name': next_ms.milestone_name,
                'due_date': next_ms.due_date,
            }

        # Collapse group_id to a single int only when exactly one group is in scope so
        # the frontend knows whether the snapshot represents one group or many.
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

    Why a dedicated endpoint instead of enhancing GET /events/v1/:
    The existing event list returns all upcoming events platform-wide. The dashboard
    needs one event personalised to the current user — a student should see their
    group's next session, not an event for a different track. Without audience filtering,
    the frontend may show a technically valid event that is irrelevant to the user.

    Relevance is determined by three OR conditions (any match qualifies):
      1. Events targeting a group the user is an active member of (EventTargetGroup).
      2. Events assigned to the user's track (Events.track FK).
      3. Events the user has an existing RSVP record for (direct invitation).

    Admin/staff users bypass the relevance filter and receive the next platform-wide event.

    Returns HTTP 204 if no relevant upcoming event exists (not an error condition).
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

        # Admins are not scoped to a group or track, so skip relevance filtering.
        if user.is_staff:
            event = base_qs.first()
            if event is None:
                return Response(None, status=status.HTTP_204_NO_CONTENT)
            return self._build_response(event, user)

        # Build relevance filter conditions as a list of Q objects that are OR-combined
        # below. Using a list instead of a single growing Q() avoids accidentally passing
        # an empty Q() to filter(), which would return every event.
        filter_conditions = []

        # Condition 1: events targeting any group the user is currently a member of.
        user_group_ids = list(
            GroupMembership.objects.filter(user=user, left_at__isnull=True)
            .values_list('group_id', flat=True)
        )
        if user_group_ids:
            group_event_ids = EventTargetGroup.objects.filter(
                group_id__in=user_group_ids
            ).values_list('event_id', flat=True)
            filter_conditions.append(Q(id__in=group_event_ids))

        # Condition 2: events whose track matches the user's assigned track.
        if user.track_id:
            filter_conditions.append(Q(track_id=user.track_id))

        # Condition 3: events the user has already been invited to or RSVPed for.
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
        """Resolve per-user context fields and serialise the event."""
        # Look up the user's RSVP for this specific event; default to 'pending' if none
        # exists (the user is relevant to the event but has not responded yet).
        rsvp = EventRsvp.objects.filter(event=event, user=user).first()
        rsvp_status = rsvp.rsvp_status if rsvp else 'pending'

        # Events.group is not a direct FK — events target groups via EventTargetGroup.
        # Return the first target group's id so the frontend can display group context.
        first_target_group = EventTargetGroup.objects.filter(event=event).first()
        group_id = first_target_group.group_id if first_target_group else None

        # Both context values are injected rather than queried inside the serializer
        # to keep the serializer stateless and avoid extra queries per serialization call.
        serializer = NextEventSerializer(
            event,
            context={'rsvp_status': rsvp_status, 'group_id': group_id},
        )
        return Response(serializer.data)
