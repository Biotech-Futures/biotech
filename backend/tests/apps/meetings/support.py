"""A group with one of each kind of person, and a way to book a meeting."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from pycrdt import Doc, Text

from apps.groups.models import GroupMembership, Groups
from apps.meetings import services
from apps.users.models import AdminScope

LIST_URL = "/api/v1/meetings/meetings/"


def detail_url(meeting, suffix=""):
    return f"{LIST_URL}{meeting.pk}/{suffix}"


def browser(state=None):
    """A browser's copy of the note, as the page builds it on connect."""
    doc = Doc()
    doc["note"] = text = Text()
    if state:
        doc.apply_update(state)
    return doc, text


def typed(doc, text, words):
    """What the page sends over the socket after typing ``words`` at the end."""
    before = doc.get_state()
    text += words
    return doc.get_update(before)


class MeetingGroupMixin:
    """mentor, supervisor and two students in one group; an outsider; an admin."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.group = Groups.objects.create(group_name="Meeting group")
        self.other_group = Groups.objects.create(group_name="Other group")
        self.mentor = User.objects.create_user(email="mentor@example.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@example.com", password="pw")
        self.student = User.objects.create_user(email="student@example.com", password="pw")
        self.classmate = User.objects.create_user(email="classmate@example.com", password="pw")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="pw")
        self.other_mentor = User.objects.create_user(email="other-mentor@example.com", password="pw")
        self.admin = User.objects.create_user(email="admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)

        roles = GroupMembership.MembershipRoleChoices
        for user, role in (
            (self.mentor, roles.MENTOR),
            (self.supervisor, roles.SUPERVISOR),
            (self.student, roles.STUDENT),
            (self.classmate, roles.STUDENT),
        ):
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)
        GroupMembership.objects.create(
            group=self.other_group, user=self.other_mentor, membership_role=roles.MENTOR
        )

    def book(self, *, start_in=timedelta(days=1), length=timedelta(minutes=30), **extra):
        start = timezone.now() + start_in
        fields = {
            "organiser": self.mentor,
            "group": self.group,
            "name": "Weekly check-in",
            "start": start,
            "end": start + length,
            "join_link": "https://zoom.us/j/123",
        }
        fields.update(extra)
        return services.schedule_meeting(**fields)
