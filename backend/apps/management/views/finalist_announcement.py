"""Notify Finalists' announcement: the in-app announcement to the finalist
groups that have been emailed, its wording (the finalist email's until
edited), and posting it (see ``services.finalist_announcement``)."""
from __future__ import annotations

import re

from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin

from ..models import FinalistAnnouncement
from ..services import finalist_announcement
from ..services.send_guard import person_name


class FinalistAnnouncementSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        # An emptied editor still leaves its tags behind.
        if not re.sub(r"<[^>]+>", "", value).strip():
            raise serializers.ValidationError("Write something to announce.")
        return value


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
