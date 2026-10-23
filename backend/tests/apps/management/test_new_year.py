"""Start new year (Management > New Year): what stops it, and what it
changes, all in one go. The year in progress is set to last calendar year,
so 1 September has always passed whatever the test clock says."""
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.announcements.models import Announcement
from apps.audit.models import AuditLog
from apps.events.models import Events
from apps.groups.models import GroupMembership, Groups
from apps.management.models import (
    CertificatesRelease,
    ChallengeYear,
    EmailSendRun,
    FinalistEmailSettings,
    MarksRelease,
    OutcomeAnnouncement,
    PresentationSettings,
    PresentationSlot,
    QueuedEmailSend,
    ResultsEmailSettings,
)
from apps.management.services.finalist_notify import SYMPOSIUM_TZ
from apps.management.services.new_year import new_year_state
from apps.resources.models import Resources
from apps.services.models import SystemEmailLog
from apps.submissions.models import Deadline, GroupExtension
from apps.submissions.services import current_cohort
from apps.resources.models import Roles
from apps.tasks.models import RoleTask, Task
from apps.users.models import (
    AdminScope,
    MentorProfile,
    RegistrationInvitation,
    RegistrationWindow,
    StudentProfile,
    SupervisorProfile,
    User,
)

URL = "/api/v1/management/new-year/"
# What a student profile needs saved.
GUARDIAN = {"pg_first_name": "Pat", "pg_last_name": "Parent", "pg_email": "pat@example.com", "school_name": "Test High", "year_lvl": "10"}


def _person(email, **extra):
    return User.objects.create_user(
        email=email, password="pw12345!", first_name="A", last_name="Person",
        account_status=User.AccountStatus.ACTIVE, is_active=True, **extra,
    )


def _signed_in(user) -> str:
    session = SessionStore()
    session["_auth_user_id"] = str(user.pk)
    session.create()
    return session.session_key


class NewYearTests(TestCase):
    def setUp(self):
        self.year = timezone.now().year - 1
        ChallengeYear.objects.create(year=self.year)
        self.admin = _person("admin-year@test.com")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def start(self, year=None):
        return self.client.post(URL, {"year": self.year + 1 if year is None else year}, format="json")

    def test_it_reads_the_year_in_progress_and_the_next(self):
        state = self.client.get(URL).json()
        self.assertEqual((state["year"], state["next_year"]), (self.year, self.year + 1))
        self.assertEqual(state["blockers"], [])

    def test_not_before_1_september_on_sydneys_calendar(self):
        def blockers(day):
            moment = datetime.combine(day, time(9), tzinfo=SYMPOSIUM_TZ)
            return new_year_state(now=moment)["blockers"]

        self.assertEqual(
            blockers(date(self.year, 8, 31)), [f"{self.year + 1} can be started from 1 September {self.year}."]
        )
        self.assertEqual(blockers(date(self.year, 9, 1)), [])

    def test_not_while_submissions_are_open(self):
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=2), grace_hours=0, is_active=True)
        response = self.start()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Submissions are still open", response.json()["detail"])
        self.assertFalse(ChallengeYear.objects.filter(year=self.year + 1).exists())

    def test_not_while_an_email_is_waiting_to_send(self):
        QueuedEmailSend.objects.create(key="finalist_notification")
        # The page checks again until it has finished.
        self.assertTrue(self.client.get(URL).json()["sending"])
        response = self.start()
        self.assertEqual(response.status_code, 400)
        self.assertIn("An email is sending", response.json()["detail"])

    def test_the_next_year_must_be_typed(self):
        student = _person("typed@test.com")
        StudentProfile.objects.create(user=student, **GUARDIAN)
        response = self.start(year=self.year)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], f"Type {self.year + 1} to confirm.")
        student.refresh_from_db()
        self.assertTrue(student.is_active)
        self.assertEqual(current_cohort(), self.year)

    def test_only_staff_can_start_it(self):
        student = _person("not-staff@test.com")
        client = APIClient()
        client.force_authenticate(student)
        self.assertEqual(client.post(URL, {"year": self.year + 1}, format="json").status_code, 403)

    def test_it_cant_start_the_same_year_twice(self):
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(self.start(year=self.year + 1).json()["detail"], f"Type {self.year + 2} to confirm.")

    def test_warnings_dont_stop_it(self):
        warnings = self.client.get(URL).json()["warnings"]
        self.assertIn("Marks haven't been released.", warnings)
        self.assertIn("Certificates haven't been released.", warnings)
        self.assertEqual(self.start().status_code, 200)


class NewYearChangesTests(TestCase):
    """Everything one press changes, and what it leaves."""

    def setUp(self):
        self.year = timezone.now().year - 1
        ChallengeYear.objects.create(year=self.year)
        now = timezone.now()
        self.admin = _person("admin-run@test.com")
        AdminScope.objects.create(user=self.admin)

        self.student = _person("student-run@test.com")
        StudentProfile.objects.create(user=self.student, **GUARDIAN)
        self.mentor = _person("mentor-run@test.com")
        MentorProfile.objects.create(user=self.mentor)
        self.supervisor = _person("supervisor-run@test.com")
        self.supervisor_profile = SupervisorProfile.objects.create(user=self.supervisor, register_after_close=True)
        # An admin who supervises too stays an admin, active.
        self.admin_supervisor = _person("admin-supervisor-run@test.com")
        AdminScope.objects.create(user=self.admin_supervisor)
        SupervisorProfile.objects.create(user=self.admin_supervisor)
        self.staff = _person("staff-run@test.com", is_staff=True)
        MentorProfile.objects.create(user=self.staff)
        self.student_session = _signed_in(self.student)
        self.admin_session = _signed_in(self.admin)

        self.group = Groups.objects.create(group_name="BTF07")
        self.deleted_group = Groups.objects.create(group_name="BTF08")
        self.deleted_group.deleted_at = timezone.now()
        self.deleted_group.save(update_fields=["deleted_at"])
        for user, role in ((self.student, "student"), (self.mentor, "mentor"), (self.supervisor, "supervisor")):
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)
        self.group_task = Task.objects.create(
            name="Draft the poster", task_type="group", group=self.group, creator_role="mentor",
        )
        self.own_task = Task.objects.create(
            name="Read the brief", task_type="individual", assigned_user=self.student, creator_role="student",
        )
        self.role_task = RoleTask.objects.create(
            name="Sign the code of conduct", role=Roles.objects.get_or_create(role_name="student")[0],
            creator_role="global_admin",
        )
        self.event = Events.objects.create(
            event_name="Kick off", event_format="virtual",
            start_datetime=now + timedelta(days=1), ends_datetime=now + timedelta(days=1, hours=1),
        )
        self.announcement = Announcement.objects.create(
            author_user=self.admin, title="Welcome", body="<p>Hi</p>", visibility_scope="global",
        )
        self.resource = Resources.objects.create(
            name="Guide", description="A guide", uploaded_by=self.admin, shown=True,
        )
        self.held_resource = Resources.objects.create(
            name="Later", description="Shown later", uploaded_by=self.admin, shown=False, release_on=date.today(),
        )

        Deadline.objects.create(closes_at=now - timedelta(days=3), grace_hours=0, is_active=True)
        self.extension = GroupExtension.objects.create(group=self.group, extended_until=now - timedelta(days=1))
        window = RegistrationWindow.objects.create(year=self.year)
        self.late_link = RegistrationInvitation.objects.create(
            window=window, token_hash="a" * 64, expires_at=now + timedelta(days=2), created_by=self.admin,
        )
        MarksRelease.objects.update_or_create(pk=1, defaults={"released_at": now, "released_by": self.admin})
        CertificatesRelease.objects.update_or_create(
            pk=1, defaults={"released_at": now, "released_by": self.admin, "exclude_finalists": False},
        )
        FinalistEmailSettings.objects.update_or_create(pk=1, defaults={
            "symposium_date": date.today(), "confirm_by": date.today(), "slides_due": date.today(),
            "registration_url": "https://example.com/symposium",
        })
        ResultsEmailSettings.objects.update_or_create(
            pk=1, defaults={"survey_url": "https://example.com/survey", "survey_closes": date.today()},
        )
        PresentationSettings.objects.update_or_create(pk=1, defaults={"times_shown": True})
        PresentationSlot.objects.create(starts_at=time(9), ends_at=time(9, 30))
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=now, finished_at=now, due=3, emailed=2, failed=1,
            error="Couldn't reach the mail server.", missed=[{"who": "(BTF07) A Person", "reason": "refused"}],
        )
        EmailSendRun.objects.create(key="bulk_email_queue", fewer_connections_until=now + timedelta(hours=1))
        OutcomeAnnouncement.objects.create(key="finalist", posted_at=now, posted_by=self.admin, title="Kept")
        SystemEmailLog.objects.create(key="announcement", missed=[{"address": "a@test.com"}])

        client = APIClient()
        client.force_authenticate(self.admin)
        with mock.patch("apps.management.services.new_year.transaction.on_commit", lambda fn: fn()):
            self.response = client.post(URL, {"year": self.year + 1}, format="json")
        self.assertEqual(self.response.status_code, 200, self.response.content)

    def test_it_moves_the_year_on_and_records_who_and_what(self):
        self.assertEqual(current_cohort(), self.year + 1)
        state = self.response.json()
        self.assertEqual((state["year"], state["next_year"]), (self.year + 1, self.year + 2))
        started = state["started"]
        self.assertEqual(started["year"], self.year + 1)
        self.assertEqual(started["started_by"], "A Person")
        self.assertEqual(started["counts"]["accounts"], 3)
        self.assertEqual(started["counts"]["groups"], 1)
        self.assertEqual(started["counts"]["tasks"], 2)
        self.assertEqual(started["counts"]["role_tasks"], 1)
        self.assertTrue(AuditLog.objects.filter(entity_type="challenge_year", action="start").exists())

    def test_people_are_deactivated_and_signed_out_but_admins_arent(self):
        for user in (self.student, self.mentor, self.supervisor):
            user.refresh_from_db()
            self.assertEqual(user.account_status, User.AccountStatus.DEACTIVATED)
            self.assertFalse(user.is_active)
        for user in (self.admin, self.admin_supervisor, self.staff):
            user.refresh_from_db()
            self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertFalse(Session.objects.filter(session_key=self.student_session).exists())
        self.assertTrue(Session.objects.filter(session_key=self.admin_session).exists())

    def test_groups_events_and_announcements_are_archived_and_resources_hidden(self):
        self.group.refresh_from_db()
        self.assertIsNotNone(self.group.archived_at)
        self.assertIsNotNone(self.group.deleted_at)
        self.assertFalse(GroupMembership.objects.filter(left_at__isnull=True).exists())
        # One deleted by hand stays deleted, not archived.
        self.deleted_group.refresh_from_db()
        self.assertIsNone(self.deleted_group.archived_at)
        # Every task, a group's, one person's or a role's.
        for task in (self.group_task, self.own_task, self.role_task):
            task.refresh_from_db()
            self.assertIsNotNone(task.archived_at)
            self.assertIsNotNone(task.deleted_at)
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.archived_at)
        self.assertIsNotNone(self.event.deleted_at)
        self.announcement.refresh_from_db()
        self.assertIsNotNone(self.announcement.archived_at)
        for resource in (self.resource, self.held_resource):
            resource.refresh_from_db()
            self.assertFalse(resource.shown)
            self.assertIsNone(resource.release_on)

    def test_new_groups_start_again_at_btf01_in_the_new_year(self):
        group = Groups.create_auto_named()
        self.assertEqual((group.group_name, group.year), ("BTF01", self.year + 1))

    def test_an_archived_group_cant_be_restored(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post(reverse("groups-restore", args=[self.group.pk]))
        self.assertEqual(response.status_code, 400)
        self.group.refresh_from_db()
        self.assertIsNotNone(self.group.deleted_at)

    def test_management_starts_again_empty(self):
        self.assertFalse(Deadline.objects.filter(is_active=True).exists())
        window = RegistrationWindow.objects.get(year=self.year + 1)
        self.assertTrue(window.closed_until_set)
        self.assertFalse(window.is_open(timezone.now()))
        self.late_link.refresh_from_db()
        self.assertIsNotNone(self.late_link.revoked_at)
        self.extension.refresh_from_db()
        self.assertIsNotNone(self.extension.revoked_at)
        self.assertIsNone(MarksRelease.load().released_at)
        certificates = CertificatesRelease.load()
        self.assertIsNone(certificates.released_at)
        self.assertFalse(certificates.exclude_finalists)
        symposium = FinalistEmailSettings.load()
        self.assertEqual(
            (symposium.symposium_date, symposium.confirm_by, symposium.slides_due, symposium.registration_url),
            (None, None, None, ""),
        )
        survey = ResultsEmailSettings.load()
        self.assertEqual((survey.survey_url, survey.survey_closes), ("", None))
        self.assertFalse(PresentationSettings.load().times_shown)
        # The presentation times stay, for the new year to use or change.
        self.assertEqual(PresentationSlot.objects.count(), 1)
        self.supervisor_profile.refresh_from_db()
        self.assertFalse(self.supervisor_profile.register_after_close)

    def test_every_emails_sent_progress_starts_again(self):
        run = EmailSendRun.objects.get(key="finalist_notification")
        self.assertEqual((run.started_at, run.due, run.emailed, run.failed, run.error, run.missed),
                         (None, 0, 0, 0, "", []))
        # The queue's own row keeps its note of the mail server pushing back.
        self.assertIsNotNone(EmailSendRun.objects.get(key="bulk_email_queue").fewer_connections_until)
        outcome = OutcomeAnnouncement.objects.get(key="finalist")
        self.assertEqual((outcome.posted_at, outcome.title), (None, "Kept"))
        self.assertEqual(SystemEmailLog.objects.get(key="announcement").missed, [])

    def test_registration_opens_again_once_its_start_is_set(self):
        window = RegistrationWindow.objects.get(year=self.year + 1)
        window.opens_at = timezone.now() - timedelta(minutes=1)
        window.save()
        self.assertTrue(window.is_open(timezone.now()))

    def test_an_archived_task_cant_be_restored(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post(f"/api/v1/tasks/{self.own_task.pk}/restore/")
        self.assertEqual(response.status_code, 400)
        self.own_task.refresh_from_db()
        self.assertIsNotNone(self.own_task.deleted_at)
