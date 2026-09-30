"""A group's marks as the marks summary and the group page's Results
section read them."""
from __future__ import annotations

from ..models import Grade, Rubric, SubmissionComponent
from . import content

# The parts whose marks are released to students and supervisors, as on the
# marks summary: not the report or prototype, whose marks stay unreleased.
RELEASED_PARTS = ("SAQ", "POSTER")


def grades_payload(group, year: int) -> list[dict]:
    """One group's marks, every part of them, for its marks summary and the
    group page's Results section.

    A criterion belongs to exactly one component, so looking a grade up by
    ``(submission_id, criterion_id)`` stays exact even though every component
    of an entry shares one submission id.
    """
    components = list(SubmissionComponent.objects.order_by("order", "id"))
    entries = {
        e.component_id: e
        for e in content.submission_entries(group_id=group.id)
    }
    feedback = content.feedback_map([group.id])
    rubrics = {
        r.component_id: r
        for r in Rubric.objects.filter(year=year, active=True).prefetch_related("criteria")
    }
    grades_by_pair: dict[tuple[int, int], Grade] = {}
    submission_ids = {e.submission_id for e in entries.values()}
    if submission_ids:
        for g in Grade.objects.filter(submission_id__in=submission_ids):
            grades_by_pair[(g.submission_id, g.criterion_id)] = g

    out = []
    for component in components:
        entry = entries.get(component.id)
        rubric = rubrics.get(component.id)
        criteria = list(rubric.criteria.all()) if rubric else []
        criteria_out = []
        for c in criteria:
            grade = grades_by_pair.get((entry.submission_id, c.id)) if entry else None
            criteria_out.append({
                "name": c.name,
                "max_mark": str(c.max_mark),
                "mark": str(grade.mark) if grade and grade.mark is not None else "",
                "comment": grade.comment if grade else "",
            })
        out.append({
            "code": component.code,
            "name": component.name,
            "submitted": entry is not None,
            "overall_comment": feedback.get((group.id, component.id), ""),
            "criteria": criteria_out,
        })
    return out
