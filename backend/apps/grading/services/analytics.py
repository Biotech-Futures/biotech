"""Analytics aggregates for the per-component dashboard (M9).

Consumed by Team 4's analytics UI. Kept a pure function so it stays trivial
to test in isolation and cheap to call — the whole cohort at capstone scale
(~180 groups × up to 15 criteria per component) fits comfortably in memory
and executes in a couple of ORM round trips.

Output shape (see :func:`compute_component_analytics`)::

    {
      "component":       {code, name, ...},
      "year":            2026,
      "criteria_total":  3,
      "groups_total":    180,
      "submissions":     {"submitted": <int>, "pending": <int>},
      "grading":         {"fully_marked": <int>,
                          "partially_marked": <int>,
                          "unmarked": <int>},
      "marks":           {"count":  <int>,
                          "mean":   <float|null>,
                          "min":    <float|null>,
                          "median": <float|null>,
                          "max":    <float|null>,
                          "histogram": [{"bucket": "0-5", "count": <int>}, ...]},
      "rankings":        [{"group_id": <int>, "group_name": <str>,
                           "total": <float>}, ...]
    }
"""
from __future__ import annotations

import statistics
from decimal import Decimal

from django.shortcuts import get_object_or_404

from apps.groups.models.groups import Groups

from ..models import Grade, Rubric, SubmissionComponent
from .content import submission_entries


DEFAULT_TOP_N = 10
DEFAULT_HISTOGRAM_BUCKETS = 10


def _histogram(values: list[float], buckets: int, low: float, high: float) -> list[dict]:
    """Return ``[{bucket: "a-b", count: n}, ...]`` histogram.

    When ``low == high`` (all-same or empty data) collapses to a single row so
    the caller doesn't have to special-case an empty response.
    """
    if not values or high <= low:
        return [{"bucket": f"{low:.2f}-{high:.2f}", "count": len(values)}]

    step = (high - low) / buckets
    edges = [low + step * i for i in range(buckets + 1)]
    counts = [0] * buckets
    for v in values:
        # Clamp to last bucket so high == max lands in the top bin, not out of range.
        idx = min(int((v - low) / step), buckets - 1)
        counts[idx] += 1
    return [
        {"bucket": f"{edges[i]:.2f}-{edges[i + 1]:.2f}", "count": counts[i]}
        for i in range(buckets)
    ]


def compute_component_analytics(
    component_code: str,
    year: int,
    *,
    top: int = DEFAULT_TOP_N,
    buckets: int = DEFAULT_HISTOGRAM_BUCKETS,
) -> dict:
    """Aggregate submission + grade stats for a single component/year."""
    component = get_object_or_404(SubmissionComponent, code=component_code)
    rubric = (
        Rubric.objects.filter(component=component, year=year, active=True)
        .prefetch_related("criteria")
        .first()
    )
    criteria = list(rubric.criteria.all()) if rubric else []
    criteria_total = len(criteria)

    groups = list(
        Groups.objects.filter(deleted_at__isnull=True)
        .order_by("group_name")
        .values("id", "group_name")
    )
    groups_total = len(groups)

    submissions = {
        e.group_id: e
        for e in submission_entries(component_code=component.code)
    }
    submitted_count = len(submissions)

    # Sum of scored marks per submission. Nulls don't count — matches the
    # per-component list view's "graded" definition so both surfaces agree.
    # The component filter is load-bearing: one submission id carries grades
    # for every component of the entry.
    grades = list(
        Grade.objects.filter(
            submission_id__in=[e.submission_id for e in submissions.values()],
            criterion__rubric__component=component,
        ).values("submission_id", "mark")
    )
    marks_by_submission: dict[int, list[Decimal]] = {}
    for g in grades:
        if g["mark"] is None:
            continue
        marks_by_submission.setdefault(g["submission_id"], []).append(g["mark"])

    fully_marked = partially_marked = unmarked = 0
    totals_per_group: list[tuple[int, str, float]] = []

    for group in groups:
        entry = submissions.get(group["id"])
        if entry is None:
            continue
        marks = marks_by_submission.get(entry.submission_id, [])
        if criteria_total > 0 and len(marks) >= criteria_total:
            fully_marked += 1
        elif marks:
            partially_marked += 1
        else:
            unmarked += 1

        if marks:
            totals_per_group.append(
                (group["id"], group["group_name"], float(sum(marks)))
            )

    totals = [t[2] for t in totals_per_group]
    if totals:
        marks_summary = {
            "count": len(totals),
            "mean": statistics.mean(totals),
            "min": min(totals),
            "median": statistics.median(totals),
            "max": max(totals),
            "histogram": _histogram(totals, buckets, min(totals), max(totals)),
        }
    else:
        marks_summary = {
            "count": 0,
            "mean": None,
            "min": None,
            "median": None,
            "max": None,
            "histogram": [],
        }

    rankings = [
        {"group_id": gid, "group_name": name, "total": total}
        for gid, name, total in sorted(
            totals_per_group, key=lambda t: t[2], reverse=True
        )[:top]
    ]

    return {
        "component": {
            "id": component.id,
            "code": component.code,
            "name": component.name,
        },
        "year": year,
        "criteria_total": criteria_total,
        "groups_total": groups_total,
        "submissions": {
            "submitted": submitted_count,
            "pending": groups_total - submitted_count,
        },
        "grading": {
            "fully_marked": fully_marked,
            "partially_marked": partially_marked,
            "unmarked": unmarked,
        },
        "marks": marks_summary,
        "rankings": rankings,
    }
