"""The grading app's one seam onto student submissions.

The student portal stores a team's entry as ONE ``submissions.Submission`` row
with per-slot fields (answers JSON, poster/report/prototype file blobs, an
optional prototype link). Grading thinks in *components* (SAQ / POSTER /
REPORT / PROTOTYPE), one rubric each. This module translates between the two:
each submitted entry is expanded into up to four :class:`ComponentEntry`
values, keyed by the ``grading_component`` catalogue's codes.

Two rules every caller can rely on:

* Only **submitted** entries appear, and only their ``submitted_*`` snapshot
  fields are read — never the editable draft. A team reopening its entry does
  not change what markers see until it submits again.
* ``submission_id`` is the ``Grade`` anchor. All of a group's entries share
  it, so per-component logic must key on ``(submission_id, component)`` — a
  criterion's component (via its rubric), never the submission alone.

Nothing else in ``apps.grading`` may import from ``apps.submissions``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.submissions.models import Submission, SubmissionQuestion
from apps.submissions.storage import submission_file_service

from ..models import ComponentFeedback, SubmissionComponent

SAQ = "SAQ"
POSTER = "POSTER"
REPORT = "REPORT"
PROTOTYPE = "PROTOTYPE"

# Component code -> the submitted-snapshot field holding its file blob.
_FILE_SLOTS = {
    POSTER: "submitted_poster",
    REPORT: "submitted_report",
    PROTOTYPE: "submitted_prototype",
}

# Component code -> the storage slot its files live under (one container each).
_STORAGE_SLOTS = {
    POSTER: "poster",
    REPORT: "report",
    PROTOTYPE: "prototype",
}


def _service_for(entry: ComponentEntry):
    return submission_file_service(_STORAGE_SLOTS[entry.component_code])


@dataclass(frozen=True)
class ComponentEntry:
    """One component of one group's submitted entry, grading's working unit."""

    submission_id: int
    group_id: int
    group_name: str
    component_id: int
    component_code: str
    submitted_at: datetime | None
    is_late: bool
    # {"storage_key", "name", "mime", "size"} for file components, else None.
    file: dict | None
    text: str  # SAQ answers flattened to readable text
    link: str  # prototype URL
    # SAQ only: the same answers structured as (prompt, answer) pairs, so the
    # marking page can render one box per question instead of parsing `text`.
    answers: tuple[tuple[str, str], ...] = ()
    # The title the team submitted; "" when it gave none.
    project_title: str = ""


def submitted_titles(group_ids) -> dict[int, str]:
    """The title each of these groups submitted, by group id; a group with
    no title (or no entry) is left out."""
    return {
        group_id: title
        for group_id, title in Submission.objects.filter(group_id__in=list(group_ids)).values_list(
            "group_id", "submitted_project_title"
        )
        if title
    }


def _answer_blocks(answers: dict) -> list[tuple[str, str]]:
    """The submitted answers JSON as ordered (prompt, answer) pairs.

    Questions supply the headings so the export means something off-platform;
    answers whose question has since been retired still appear, labelled by
    their raw key rather than silently dropped.
    """
    if not answers:
        return []
    prompts = {q.key: q.prompt for q in SubmissionQuestion.objects.all()}
    ordered = [q.key for q in SubmissionQuestion.objects.order_by("order", "id")]
    keys = [k for k in ordered if k in answers]
    keys += [k for k in answers if k not in prompts]
    blocks = []
    for key in keys:
        value = str(answers.get(key) or "").strip()
        if not value:
            continue
        blocks.append((prompts.get(key, key), value))
    return blocks


def _flatten_answers(answers: dict) -> str:
    """Marker-readable text form of the answers (exports, zip text.txt)."""
    return "\n\n".join(f"{prompt}\n{value}" for prompt, value in _answer_blocks(answers))


def _expand(submission: Submission, components: list[SubmissionComponent]) -> list[ComponentEntry]:
    entries = []
    common = {
        "submission_id": submission.id,
        "group_id": submission.group_id,
        "group_name": submission.group.group_name,
        "project_title": submission.submitted_project_title,
        "submitted_at": submission.submitted_at,
        "is_late": submission.is_late,
    }
    for component in components:
        file_blob = None
        text = ""
        link = ""
        answer_blocks: tuple[tuple[str, str], ...] = ()
        if component.code == SAQ:
            blocks = _answer_blocks(submission.submitted_answers or {})
            if not blocks:
                continue
            answer_blocks = tuple(blocks)
            text = "\n\n".join(f"{prompt}\n{value}" for prompt, value in blocks)
        elif component.code in _FILE_SLOTS:
            file_blob = getattr(submission, _FILE_SLOTS[component.code]) or None
            if component.code == PROTOTYPE:
                link = submission.submitted_prototype_url or ""
            if not file_blob and not link:
                continue
        else:
            # A component the catalogue grew that no slot feeds yet: nothing
            # to show, but rubric/grade plumbing elsewhere still works.
            continue
        entries.append(ComponentEntry(
            component_id=component.id,
            component_code=component.code,
            file=file_blob,
            text=text,
            link=link,
            answers=answer_blocks,
            **common,
        ))
    return entries


def submission_entries(
    *,
    component_code: str | None = None,
    group_id: int | None = None,
    group_ids: list[int] | None = None,
    submission_ids: list[int] | None = None,
) -> list[ComponentEntry]:
    """Every submitted component entry matching the filters.

    Ordered by group name then component order, so exports are stable.
    """
    components = list(SubmissionComponent.objects.order_by("order", "id"))
    if component_code is not None:
        components = [c for c in components if c.code == component_code]
        if not components:
            return []

    qs = (
        Submission.objects.filter(submitted_at__isnull=False)
        .select_related("group")
        .filter(group__deleted_at__isnull=True)
        .order_by("group__group_name", "group_id")
    )
    if group_id is not None:
        qs = qs.filter(group_id=group_id)
    if group_ids:
        qs = qs.filter(group_id__in=group_ids)
    if submission_ids:
        qs = qs.filter(id__in=submission_ids)

    entries: list[ComponentEntry] = []
    for submission in qs:
        entries.extend(_expand(submission, components))
    return entries


def entries_by_submission(entries: list[ComponentEntry]) -> dict[int, list[ComponentEntry]]:
    """Group entries by their shared submission id, for grade validation."""
    out: dict[int, list[ComponentEntry]] = {}
    for entry in entries:
        out.setdefault(entry.submission_id, []).append(entry)
    return out


def file_url(entry: ComponentEntry, *, as_attachment: bool = False) -> str | None:
    """Resolve the entry's file to a fetchable URL (SAS-signed on Azure).

    None when there is no file or the storage backend cannot sign — the
    marking payload says "unavailable" rather than 500ing (matches how the
    rest of the codebase treats missing blobs).
    """
    if not entry.file:
        return None
    return _service_for(entry).resolve_url(
        entry.file.get("storage_key"),
        filename=entry.file.get("name"),
        content_type=entry.file.get("mime"),
        as_attachment=as_attachment,
    )


def open_file(entry: ComponentEntry):
    """Open the entry's file for streaming (zip exports). Caller closes."""
    if not entry.file or not entry.file.get("storage_key"):
        raise FileNotFoundError("entry has no stored file")
    return _service_for(entry).open(entry.file["storage_key"])


def entry_payload(
    entry: ComponentEntry | None, overall_comment: str = "", *, closes_at=None
) -> dict | None:
    """The marking API's per-component ``submission`` block.

    Field-compatible with the retired per-component SubmissionSerializer so
    the adminweb marking UI needs no changes.
    """
    if entry is None:
        return None
    return {
        "id": entry.submission_id,
        "component": entry.component_id,
        "file_url": file_url(entry),
        # Attachment variant of the SUBMITTED file's URL — deliberately not the
        # portal's /files/<slot>/download/ endpoint, which serves the editable
        # draft and could diverge from the snapshot during a reopen.
        "file_download_url": file_url(entry, as_attachment=True),
        "file_name": (entry.file or {}).get("name"),
        "text": entry.text,
        # SAQ: per-question blocks so the page can box each answer; the flat
        # `text` above stays for exports and older consumers.
        "answers": [
            {"prompt": prompt, "answer": answer} for prompt, answer in entry.answers
        ] or None,
        "link": entry.link,
        "submitted_at": entry.submitted_at,
        "is_late": is_late_against(entry, closes_at),
        "overall_comment": overall_comment,
    }


def late_by_label(delta) -> str:
    """'5d 1h' / '22h 54m' / '45m' — how far past the deadline a submit
    landed. Minutes are dropped once a full day has passed; at that scale
    they are noise in the tables."""
    total_minutes = max(0, int(delta.total_seconds() // 60))
    days, rest = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return "<1m"


def is_late_against(entry: ComponentEntry, closes_at) -> bool:
    """Lateness derived directly from times: submitted after the deadline in
    force for the group (extension-aware). Derived at read time rather than
    read from the stored ``is_late`` flag, so entries submitted before the
    flag was recorded correctly still display right.
    """
    return (
        entry.submitted_at is not None
        and closes_at is not None
        and entry.submitted_at > closes_at
    )


def lateness_label(entry: ComponentEntry, closes_at) -> str | None:
    """The row's late label: None on time, else e.g. '3h 12m'."""
    if not is_late_against(entry, closes_at):
        return None
    return late_by_label(entry.submitted_at - closes_at)


def has_submitted(group_id: int) -> bool:
    """Whether the team's entry was submitted (a frozen snapshot exists)."""
    return Submission.objects.filter(
        group_id=group_id, submitted_at__isnull=False
    ).exists()


def group_deadline_map(group_ids: list[int]) -> dict[int, "datetime | None"]:
    """The GLOBAL announced closing time, per group.

    Deliberately ignores per-group extensions: lateness is always judged
    against the global deadline — an extension only keeps the portal
    accepting, it does not make a submission on time. ``None`` when no
    deadline is configured at all.
    """
    from apps.submissions.models import Deadline

    baseline = Deadline.objects.filter(is_active=True).order_by("-created_at").first()
    default = baseline.closes_at if baseline else None
    return {gid: default for gid in group_ids}


def feedback_map(group_ids: list[int] | None = None) -> dict[tuple[int, int], str]:
    """``{(group_id, component_id): comment}`` for the given groups (or all)."""
    qs = ComponentFeedback.objects.all()
    if group_ids is not None:
        qs = qs.filter(group_id__in=group_ids)
    return {
        (row["group_id"], row["component_id"]): row["comment"]
        for row in qs.values("group_id", "component_id", "comment")
    }
