"""Finalist flagging. The finalist email and Notify Finalists are
Management's (``apps.management.views.finalist``).

Admins mark the top ~30 groups as finalists after marking closes. Flagging is
idempotent — re-POSTing an already-flagged group updates ``flagged_at`` and
optionally re-fires the notification. The ``notified`` bool on the flag lets
the notification path avoid spamming groups when admins toggle repeatedly.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups
from apps.management.services.finalist_notify import notify_finalist
from apps.management.services.send_guard import (
    FINALIST_SEND,
    AlreadySending,
    holding_send,
    submissions_open_reason,
)
from apps.management.services.symposium_emails import member_ids, role_counts

from ..models import (
    FinalistFlag,
    Grade,
    GroupMarkingCategories,
    Rubric,
    SubmissionComponent,
)
from ..permissions import IsGrader
from ..services import content
from ..services.xlsx import _format_product_category, _format_solution_category

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
        flags = list(
            FinalistFlag.objects.select_related("group", "flagged_by", "notified_by")
            .order_by("group__group_name")
        )
        # Students, mentors and supervisors on each team who have an address
        # to be emailed at.
        members = member_ids(f.group_id for f in flags)
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
                    "students": len(members["students"].get(f.group_id, ())),
                }
                for f in flags
            ],
            # Everyone due the email and emailed, by role; a notified team's
            # members count as emailed (see ``role_counts``).
            "counts": role_counts(
                members, [f.group_id for f in flags], {f.group_id for f in flags if f.notified}
            ),
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
             "incomplete": ["REPORT", ...],            # entered, not fully marked
             "project_title": "Plant Sensors" | "",    # as submitted
             "project_category": "Health and Medicine" | "",
             "solution_category": "App" | "",
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
        # Only components that can actually carry marks appear as columns.
        # REPORT and PROTOTYPE have rubrics but no criteria (their marks are
        # never released), so a marks column for them would always be empty.
        markable_ids = set(
            Rubric.objects.filter(active=True, criteria__isnull=False)
            .values_list("component_id", flat=True)
        )
        components = [
            c for c in SubmissionComponent.objects.order_by("order", "id")
            if c.id in markable_ids
        ]
        code_by_component = {c.id: c.code for c in components}
        groups = list(
            Groups.objects.filter(deleted_at__isnull=True)
            .order_by("group_name")
            .values("id", "group_name")
        )
        entries = content.submission_entries()
        group_by_submission = {e.submission_id: e.group_id for e in entries}

        # One submitted_at per group — shared by all its entries.
        submit_meta = {e.group_id: e.submitted_at for e in entries}
        deadlines = content.group_deadline_map(list(submit_meta)) if submit_meta else {}

        # One submission id spans an entry's components, so totals must split
        # by the criterion's component or every column would show the same sum.
        mark_rows = list(
            Grade.objects.filter(mark__isnull=False)
            .values("submission_id", "criterion__rubric__component_id")
            .annotate(total=Sum("mark"), scored=Count("id"))
        )
        totals = {
            (row["submission_id"], row["criterion__rubric__component_id"]): row["total"]
            for row in mark_rows
        }
        # How many criteria of each part are scored, to spot parts still being marked.
        scored = {
            (row["submission_id"], row["criterion__rubric__component_id"]): row["scored"]
            for row in mark_rows
        }

        # "SAQ 1" / "POSTER 3" labels: rubric position per criterion, prefixed
        # with the component code since this table spans several components.
        criterion_labels: dict[int, tuple[str, int, int]] = {}
        criteria_count: dict[str, int] = {}
        for component_index, component in enumerate(components):
            rubric = (
                Rubric.objects.filter(component=component, active=True)
                .prefetch_related("criteria")
                .first()
            )
            if rubric is None:
                continue
            for i, criterion in enumerate(rubric.criteria.all(), start=1):
                criterion_labels[criterion.id] = (component.code, component_index, i)
            criteria_count[component.code] = len(rubric.criteria.all())

        markers_by_group: dict[int, list[str]] = {}
        criterion_markers_by_group: dict[int, list[dict]] = {}
        grader_rows = (
            Grade.objects.filter(mark__isnull=False, graded_by__isnull=False)
            .order_by("-graded_at")
            .values(
                "submission_id",
                "criterion_id",
                "graded_by__first_name",
                "graded_by__last_name",
            )
        )
        for row in grader_rows:
            group_id = group_by_submission.get(row["submission_id"])
            if group_id is None:
                continue
            name = f'{row["graded_by__first_name"]} {row["graded_by__last_name"]}'.strip()
            if not name:
                continue
            names = markers_by_group.setdefault(group_id, [])
            if name not in names:
                names.append(name)
            labeled = criterion_labels.get(row["criterion_id"])
            if labeled is not None:
                code, component_index, position = labeled
                criterion_markers_by_group.setdefault(group_id, []).append(
                    {"label": f"{code} {position}", "marker": name,
                     "_sort": (component_index, position)}
                )
        for markers in criterion_markers_by_group.values():
            markers.sort(key=lambda m: m.pop("_sort"))

        marks_by_group: dict[int, dict[str, object]] = {}
        for (submission_id, component_id), total in totals.items():
            group_id = group_by_submission.get(submission_id)
            code = code_by_component.get(component_id)
            if group_id is None or code is None:
                continue
            marks_by_group.setdefault(group_id, {})[code] = total

        finalist_ids = set(FinalistFlag.objects.values_list("group_id", flat=True))
        # The title each team submitted, as the entry being marked has it.
        titles = content.submitted_titles(g["id"] for g in groups)
        # The categories picked on the marking key.
        categories = {
            c.group_id: c
            for c in GroupMarkingCategories.objects.filter(group_id__in=[g["id"] for g in groups])
        }
        submitted_group_ids = {e.group_id for e in entries}
        # Parts a team handed in that still have unscored criteria (including
        # parts nobody has started), so the table can flag them apart from
        # parts never sent.
        incomplete_codes: dict[int, set[str]] = {}
        for e in entries:
            if scored.get((e.submission_id, e.component_id), 0) < criteria_count.get(
                e.component_code, 0
            ):
                incomplete_codes.setdefault(e.group_id, set()).add(e.component_code)

        rows = []
        for g in groups:
            marks = marks_by_group.get(g["id"], {})
            overall = sum(marks.values()) if marks else None
            submitted_at = submit_meta.get(g["id"])
            closes_at = deadlines.get(g["id"])
            # Derived from times, not the stored flag — matches the component
            # tables, and entries recorded before the flag worked display right.
            is_late = (
                submitted_at is not None
                and closes_at is not None
                and submitted_at > closes_at
            )
            late_by = content.late_by_label(submitted_at - closes_at) if is_late else None
            rows.append({
                "group_id": g["id"],
                "group_name": g["group_name"],
                "is_late": is_late,
                # e.g. "3h 12m"; "" when the amount can't be derived any more;
                # null for on-time or unsubmitted rows.
                "late_by": late_by,
                "marks": {
                    c.code: (self._fmt(marks[c.code]) if c.code in marks else None)
                    for c in components
                },
                "total": self._fmt(overall) if overall is not None else None,
                "markers": markers_by_group.get(g["id"], []),
                # [{"label": "SAQ 1", "marker": "Ada"}, ...] in rubric order.
                "criterion_markers": criterion_markers_by_group.get(g["id"], []),
                "project_title": titles.get(g["id"]) or "",
                "project_category": _format_product_category(categories.get(g["id"])),
                "solution_category": _format_solution_category(categories.get(g["id"])),
                "is_finalist": g["id"] in finalist_ids,
                "has_submission": g["id"] in submitted_group_ids,
                "incomplete": [
                    c.code for c in components if c.code in incomplete_codes.get(g["id"], ())
                ],
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
        # The team is flagged either way; the email waits for submissions to
        # close, and for any send already running.
        if should_notify and not submissions_open_reason():
            try:
                with holding_send(FINALIST_SEND):
                    notify_finalist(flag, actor=request.user)
            except AlreadySending:
                pass
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
