"""Finalist flagging.

Admins mark the top ~30 groups as finalists after marking closes. Flagging is
idempotent — re-POSTing an already-flagged group updates ``flagged_at`` and
optionally re-fires the notification. The ``notified`` bool on the flag lets
the notification path avoid spamming groups when admins toggle repeatedly.

Notification is env-gated by ``GRADING_FINALIST_EMAIL_ENABLED`` so local dev
never accidentally emails real people; toggle explicitly per environment.
"""
from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups

from ..models import FinalistFlag
from ..permissions import IsGrader
from ..services.finalist_notify import notify_finalist


class FinalistListView(APIView):
    """GET /api/v1/grading/finalists/ — list every currently-flagged group."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @staticmethod
    def _user_name(user) -> str | None:
        if user is None:
            return None
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.email

    def get(self, request):
        flags = (
            FinalistFlag.objects.select_related("group", "flagged_by", "notified_by")
            .order_by("group__group_name")
        )
        return Response({
            "finalists": [
                {
                    "group_id": f.group_id,
                    "group_name": f.group.group_name,
                    "flagged_at": f.flagged_at,
                    "flagged_by": self._user_name(f.flagged_by),
                    "notified": f.notified,
                    "notified_at": f.notified_at,
                    "notified_by": self._user_name(f.notified_by),
                }
                for f in flags
            ]
        })


class FinalistNotifyAllView(APIView):
    """POST /api/v1/grading/finalists/notify/ — email finalist teams that
    haven't been notified yet.

    Optional body ``{"group_ids": [1, 2, ...]}`` restricts the send to those
    groups; omitted or empty means every un-notified finalist.

    ``notify_finalist`` is a no-op per flag when it was already notified or
    when ``GRADING_FINALIST_EMAIL_ENABLED`` is off, so this is safe to press
    repeatedly.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request):
        flags = FinalistFlag.objects.select_related("group").filter(notified=False)
        group_ids = request.data.get("group_ids")
        if group_ids:
            if not isinstance(group_ids, list) or not all(isinstance(g, int) for g in group_ids):
                return Response(
                    {"detail": "group_ids must be a list of integers"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            flags = flags.filter(group_id__in=group_ids)
        sent = sum(1 for flag in flags if notify_finalist(flag, actor=request.user))
        return Response({
            "sent": sent,
            "pending": FinalistFlag.objects.filter(notified=False).count(),
        })


class FinalistToggleView(APIView):
    """POST/DELETE /api/v1/grading/groups/<id>/finalist/

    POST body:
        ``{"notify": true|false}`` — optional; default false.

    POST is upsert semantics. DELETE unflags (idempotent 204 either way —
    unflagging a non-flagged group is a no-op, not an error, so double-clicks
    don't 500).
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @transaction.atomic
    def post(self, request, group_id: int):
        group = get_object_or_404(Groups.objects.filter(deleted_at__isnull=True), pk=group_id)
        flag, created = FinalistFlag.objects.select_for_update().get_or_create(
            group=group,
            defaults={"flagged_by": request.user},
        )
        if not created:
            flag.flagged_at = timezone.now()
            flag.flagged_by = request.user
            flag.save(update_fields=["flagged_at", "flagged_by"])

        should_notify = bool(request.data.get("notify"))
        notified_now = False
        if should_notify:
            notify_finalist(flag, actor=request.user)
            notified_now = flag.notified  # notify_finalist sets it if it actually sent

        return Response(
            {
                "group_id": flag.group_id,
                "flagged_at": flag.flagged_at,
                "notified": flag.notified,
                "notified_now": notified_now,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, group_id: int):
        FinalistFlag.objects.filter(group_id=group_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
