"""Announcements to this year's finalist, non-finalist and non-submission
groups: Notify Finalists' announcement to the finalist groups emailed, its
wording (the finalist email's until edited) and posting it (see
``services.finalist_announcement``); and those three groups as categories
New Announcement can target."""
from __future__ import annotations

import re
from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.groups.models.groups import Groups
from apps.services.system_email import clean_email_body
from apps.submissions.services import active_deadline, current_cohort

from ..models import FinalistAnnouncement
from ..services import finalist_announcement
from ..services.send_guard import _long_time, person_name
from ..services.symposium_emails import NONFINALIST, NONSUBMISSION


class FinalistAnnouncementSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        # An emptied editor still leaves its tags behind.
        if not re.sub(r"<[^>]+>", "", value).strip():
            raise serializers.ValidationError("Write something to announce.")
        # Keeps its boxes and buttons, and strips scripts, event handlers and
        # javascript: URLs, as System Emails does: announcements show as is.
        return clean_email_body(value)


def _payload() -> dict:
    row = FinalistAnnouncement.load()
    title, body = finalist_announcement.wording(row)
    return {
        "title": title,
        "body": body,
        # Changed from the finalist email's wording.
        "edited": row.edited_at is not None,
        # The groups it goes to: the finalist groups emailed so far.
        "groups": len(finalist_announcement.notified_group_ids()),
        "posted_at": row.posted_at,
        "posted_by": person_name(row.posted_by) if row.posted_by else None,
    }


class FinalistAnnouncementView(APIView):
    """GET/PATCH/DELETE /api/v1/management/finalists/announcement/ — its
    wording and when it was last posted; PATCH saves an edited title and body,
    DELETE goes back to the finalist email's wording."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response(_payload())

    def patch(self, request):
        serializer = FinalistAnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = FinalistAnnouncement.load()
        row.title = serializer.validated_data["title"]
        row.body = serializer.validated_data["body"]
        row.edited_at = timezone.now()
        row.save()
        return Response(_payload())

    def delete(self, request):
        row = FinalistAnnouncement.load()
        row.title, row.body, row.edited_at = "", "", None
        row.save()
        return Response(_payload())


class FinalistAnnouncementPostView(APIView):
    """POST /api/v1/management/finalists/announcement/post/ — post it to the
    finalist groups emailed so far, or update the one already posted."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        try:
            finalist_announcement.post(request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_payload())


# --- New Announcement's categories ----------------------------------------------------

NO_DEADLINE = "Available once a submission deadline is set and has passed."


def _category_groups(year: int) -> dict:
    """This year's groups in each category: picked as finalists, submitted
    but not picked, and didn't submit (as Email Nonfinalist counts them)."""
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
