"""Announcements to this year's groups: the announcement that goes with each
email telling groups their Challenge outcome (finalist, non-finalist,
non-submission, and the results emails to groups and to supervisors), its
wording (the email's until edited) and posting it to whoever the email
reached (see ``services.outcome_announcement``); and the finalist,
non-finalist and non-submission groups as categories New Announcement can
target."""
from __future__ import annotations

import re
from datetime import timedelta

from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.groups.models.groups import Groups
from apps.services.system_email import clean_email_body
from apps.submissions.services import active_deadline, current_cohort

from ..services import outcome_announcement
from ..services.send_guard import _long_time, person_name
from ..services.symposium_emails import NONFINALIST, NONSUBMISSION


class OutcomeAnnouncementSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        # An emptied editor still leaves its tags behind.
        if not re.sub(r"<[^>]+>", "", value).strip():
            raise serializers.ValidationError("Write something to announce.")
        # Keeps its boxes and buttons, and strips scripts, event handlers and
        # javascript: URLs, as System Emails does: announcements show as is.
        return clean_email_body(value)


def _kind(kind: str) -> str:
    if kind not in outcome_announcement.KINDS:
        raise Http404
    return kind


def _payload(kind: str) -> dict:
    row = outcome_announcement.load(kind)
    title, body = outcome_announcement.wording(row)
    group_ids, user_ids = outcome_announcement.KINDS[kind].audience()
    return {
        "title": title,
        "body": body,
        # Changed from the email's wording.
        "edited": row.edited_at is not None,
        # Who it goes to: the groups, or supervisors, the email reached so far.
        "recipients": len(group_ids) + len(user_ids),
        "noun": outcome_announcement.KINDS[kind].noun,
        "posted_at": row.posted_at,
        "posted_by": person_name(row.posted_by) if row.posted_by else None,
    }


class OutcomeAnnouncementView(APIView):
    """GET/PATCH/DELETE /api/v1/management/outcome-announcements/<kind>/ — its
    wording and when it was last posted; PATCH saves an edited title and body,
    DELETE goes back to the email's wording. ``kind`` is a key of
    ``outcome_announcement.KINDS``, e.g. ``finalists``."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, kind: str):
        return Response(_payload(_kind(kind)))

    def patch(self, request, kind: str):
        kind = _kind(kind)
        serializer = OutcomeAnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = outcome_announcement.load(kind)
        row.title = serializer.validated_data["title"]
        row.body = serializer.validated_data["body"]
        row.edited_at = timezone.now()
        row.save()
        return Response(_payload(kind))

    def delete(self, request, kind: str):
        kind = _kind(kind)
        row = outcome_announcement.load(kind)
        row.title, row.body, row.edited_at = "", "", None
        row.save()
        return Response(_payload(kind))


class OutcomeAnnouncementPostView(APIView):
    """POST /api/v1/management/outcome-announcements/<kind>/post/ — post it to
    whoever the email reached so far, or update the one already posted."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, kind: str):
        kind = _kind(kind)
        try:
            outcome_announcement.post(kind, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_payload(kind))


# --- New Announcement's categories ----------------------------------------------------

NO_DEADLINE = "Available once a submission deadline is set and has passed."


def _category_groups(year: int) -> dict:
    """This year's groups in each category: picked as finalists, submitted
    but not picked, and didn't submit (as Notify Nonfinalist counts them)."""
    finalists = Groups.objects.filter(deleted_at__isnull=True, year=year, finalist_flag__isnull=False)
    return {
        "finalists": finalists,
        "nonfinalists": NONFINALIST.teams(year),
        "nonsubmissions": NONSUBMISSION.teams(year),
    }


CATEGORY_LABELS = {"finalists": "Finalist", "nonfinalists": "Nonfinalist", "nonsubmissions": "Nonsubmission"}


class AnnouncementCategoriesView(APIView):
    """GET /api/v1/management/announcement-categories/ — the finalist,
    non-finalist and non-submission groups New Announcement can target, each
    with its groups' ids. Only once the submission deadline, grace hours
    included, has passed: until then who is in which isn't settled, and
    ``available`` is false with why."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        deadline = active_deadline()
        reason = NO_DEADLINE
        if deadline is not None:
            until = deadline.closes_at + timedelta(hours=deadline.grace_hours)
            reason = (
                "" if timezone.now() > until
                else f"Available once submissions close, on {_long_time(until)} (Sydney time)."
            )
        groups = _category_groups(current_cohort()) if not reason else {}
        return Response({
            "available": not reason,
            "reason": reason,
            "categories": [
                {
                    "key": key,
                    "label": label,
                    "group_ids": sorted(groups[key].values_list("id", flat=True)) if key in groups else [],
                }
                for key, label in CATEGORY_LABELS.items()
            ],
        })
