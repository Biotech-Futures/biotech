"""Finalist flagging.

Admins mark the top ~30 groups as finalists after marking closes. Flagging is
idempotent — re-POSTing an already-flagged group updates ``flagged_at`` and
optionally re-fires the notification. The ``notified`` bool on the flag lets
the notification path avoid spamming groups when admins toggle repeatedly.

Notification is env-gated by ``GRADING_FINALIST_EMAIL_ENABLED`` so local dev
never accidentally emails real people; toggle explicitly per environment.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups
from apps.submissions.models import Submission

from ..models import SubmissionComponent

from ..models import FinalistFlag, Grade
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


class FinalistCandidatesView(APIView):
    """GET /api/v1/grading/finalists/candidates/ — every group with its mark
    total per component, the overall total, and who marked it. The ranking
    table admins use to decide which groups to flag as finalists.

    Shape:
        {
          "components": [{"code": "SAQ", "name": "..."}, ...],
          "rows": [
            {"group_id", "group_name",
             "marks": {"SAQ": "12.50" | null, ...},   # sum of scored marks
             "total": "31.00" | null,                  # sum across components
             "markers": ["Ada Grader", ...],           # deduped, latest first
             "is_finalist": bool}
          ]
        }

    Rows are sorted by total (highest first); ungraded groups sink to the
    bottom alphabetically.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @staticmethod
    def _fmt(value) -> str:
        # SQLite aggregates lose the decimal scale ("12.5"); pin to 2 dp.
        return str(Decimal(value).quantize(Decimal("0.01")))

    def get(self, request):
        components = list(SubmissionComponent.objects.order_by("order", "id"))
        code_by_component = {c.id: c.code for c in components}
        groups = list(
            Groups.objects.filter(deleted_at__isnull=True)
            .order_by("group_name")
            .values("id", "group_name")
        )
        submissions = list(Submission.objects.values("id", "group_id", "component_id"))
        sub_meta = {s["id"]: s for s in submissions}

        totals_by_sub = {
            row["submission_id"]: row["total"]
            for row in Grade.objects.filter(mark__isnull=False)
            .values("submission_id")
            .annotate(total=Sum("mark"))
        }

        markers_by_group: dict[int, list[str]] = {}
        grader_rows = (
            Grade.objects.filter(mark__isnull=False, graded_by__isnull=False)
            .order_by("-graded_at")
            .values("submission_id", "graded_by__first_name", "graded_by__last_name")
        )
        for row in grader_rows:
            meta = sub_meta.get(row["submission_id"])
            if meta is None:
                continue
            name = f'{row["graded_by__first_name"]} {row["graded_by__last_name"]}'.strip()
            if not name:
                continue
            names = markers_by_group.setdefault(meta["group_id"], [])
            if name not in names:
                names.append(name)

        marks_by_group: dict[int, dict[str, object]] = {}
        for s in submissions:
            total = totals_by_sub.get(s["id"])
            if total is None:
                continue
            marks_by_group.setdefault(s["group_id"], {})[code_by_component[s["component_id"]]] = total

        finalist_ids = set(FinalistFlag.objects.values_list("group_id", flat=True))
        submitted_group_ids = {s["group_id"] for s in submissions}

        rows = []
        for g in groups:
            marks = marks_by_group.get(g["id"], {})
            overall = sum(marks.values()) if marks else None
            rows.append({
                "group_id": g["id"],
                "group_name": g["group_name"],
                "marks": {
                    c.code: (self._fmt(marks[c.code]) if c.code in marks else None)
                    for c in components
                },
                "total": self._fmt(overall) if overall is not None else None,
                "markers": markers_by_group.get(g["id"], []),
                "is_finalist": g["id"] in finalist_ids,
                "has_submission": g["id"] in submitted_group_ids,
            })
        rows.sort(
            key=lambda r: (
                r["total"] is None,
                -float(r["total"]) if r["total"] is not None else 0.0,
                r["group_id"],
            )
        )

        return Response({
            "components": [{"code": c.code, "name": c.name} for c in components],
            "rows": rows,
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
