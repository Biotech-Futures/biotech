import csv
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.announcements.models import Announcement, AnnouncementDelivery
from apps.audit.models import AuditLog
from apps.chat.models import Messages
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope, AreasOfInterest, StudentProfile, UserInterest


User = get_user_model()


class ReportExportApiTests(APITestCase):
    url = "/api/v1/admin/analytics/reports/export/"

    def setUp(self):
        self.admin = User.objects.create_user(
            email="reports.admin@example.com",
            password="pass1234",
            first_name="Reports",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.non_admin = User.objects.create_user(
            email="reports.user@example.com",
            password="pass1234",
            first_name="Reports",
            last_name="User",
        )
        self.au = Countries.objects.create(country_name="Australia")
        self.us = Countries.objects.create(country_name="United States")
        self.nsw = CountryStates.objects.create(
            country=self.au,
            state_name="NSW",
        )
        self.student_role = Roles.objects.create(role_name="student")
        self.mentor_role = Roles.objects.create(role_name="mentor")

        self.student_granted = self._user(
            "granted@example.com", self.au, self.nsw, User.AccountStatus.ACTIVE
        )
        self.student_not_granted = self._user(
            "not-granted@example.com",
            self.au,
            self.nsw,
            User.AccountStatus.PENDING,
            password=None,
        )
        self.mentor = self._user(
            "mentor@example.com", self.us, None, User.AccountStatus.ACTIVE
        )
        self._assign(self.student_granted, self.student_role)
        self._assign(self.student_not_granted, self.student_role)
        self._assign(self.mentor, self.mentor_role)

        StudentProfile.objects.create(
            user=self.student_granted,
            pg_first_name="Parent",
            pg_last_name="Granted",
            parent_guardian_flag=True,
            school_name="School",
            year_lvl="10",
            has_join_permission=True,
        )
        StudentProfile.objects.create(
            user=self.student_not_granted,
            pg_first_name="Parent",
            pg_last_name="Pending",
            parent_guardian_flag=False,
            school_name="School",
            year_lvl="11",
            has_join_permission=False,
        )
        biology = AreasOfInterest.objects.create(interest_desc="Biology")
        risky = AreasOfInterest.objects.create(interest_desc="=Formula")
        UserInterest.objects.create(user=self.student_granted, interest=biology)
        UserInterest.objects.create(user=self.student_not_granted, interest=risky)

    def _user(self, email, country, state, account_status, password="pass1234"):
        return User.objects.create_user(
            email=email,
            password=password,
            first_name="Report",
            last_name="Person",
            country=country,
            state=state,
            account_status=account_status,
        )

    def _assign(self, user, role):
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=timezone.now() - timedelta(days=1),
        )

    def _get(self, params):
        self.client.force_authenticate(user=self.admin)
        return self.client.get(self.url, params)

    def _csv(self, response):
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
        raw = content.decode("utf-8-sig")
        return list(csv.DictReader(StringIO(raw))), raw

    def test_user_csv_login_percentage_excludes_previous_year_logins(self):
        year = timezone.now().year
        User.objects.filter(pk=self.student_granted.pk).update(
            last_login=datetime(year - 1, 12, 31, tzinfo=datetime_timezone.utc))
        User.objects.filter(pk=self.mentor.pk).update(last_login=timezone.now())
        response = self._get({"report": "users", "year": year})
        self.assertEqual(response.status_code, 200)
        text = self._csv(response)[1]
        self.assertIn("Students Logged In (%),0", text)
        self.assertIn("Mentors Logged In (%),100", text)

    def test_vue_page_reports_keep_current_csv_content_and_filenames(self):
        year = timezone.now().year
        self.student_granted.last_login = timezone.now()
        self.student_granted.save(update_fields=["last_login"])
        group = Groups.objects.create(group_name="Report group")
        for index in range(3):
            Groups.objects.create(group_name=f"Empty group {index}")
        GroupMembership.objects.create(group=group, user=self.student_granted, membership_role="student")
        GroupMembership.objects.create(group=group, user=self.mentor, membership_role="mentor")

        users = self._get({"report": "users", "year": year})
        self.assertEqual(users.status_code, 200)
        self.assertIn(f'users-analytics-{year}.csv', users["Content-Disposition"])
        self.assertIn("Total Users,3", self._csv(users)[1])
        self.assertIn("Students Logged In (%),50", self._csv(self._get({"report": "users", "year": year}))[1])

        groups = self._get({"report": "groups", "year": year})
        self.assertEqual(groups.status_code, 200)
        self.assertIn(f'groups-analytics-{year}.csv', groups["Content-Disposition"])
        self.assertIn("Groups with Mentor,1", self._csv(groups)[1])
        self.assertIn("Average Group Size,0.3", self._csv(self._get({"report": "groups", "year": year}))[1])

        overview = self._get({"report": "overview", "year": year, "registration_period": "year"})
        self.assertEqual(overview.status_code, 200)
        self.assertIn(f'biotech-analytics-{year}.csv', overview["Content-Disposition"])
        self.assertIn("Metric,Value,Notes,Data Source", self._csv(overview)[1])

        messages = self._get({
            "report": "messages", "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31", "interval": "month", "mode": "groups",
        })
        self.assertEqual(messages.status_code, 200)
        self.assertIn(f'messages-analytics-groups-{year}-12-31.csv', messages["Content-Disposition"])
        self.assertIn("Messages This Period,0", self._csv(messages)[1])
        self.assertIn("Report group", self._csv(self._get({
            "report": "messages", "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31", "interval": "month", "mode": "groups",
        }))[1])

    def test_messages_page_export_applies_group_and_user_filters(self):
        now = timezone.now()
        first = Groups.objects.create(group_name="First group")
        second = Groups.objects.create(group_name="=Formula group")
        for group, user in ((first, self.student_granted), (second, self.mentor)):
            GroupMembership.objects.create(group=group, user=user, membership_role="student")
        Messages.objects.create(group=first, sender_user=self.student_granted, message_text="first", sent_at=now)
        Messages.objects.create(group=second, sender_user=self.mentor, message_text="second", sent_at=now)
        base = {"report": "messages", "start_date": now.date().isoformat(),
                "end_date": now.date().isoformat(), "anchor_date": now.date().isoformat(), "interval": "day"}

        groups = self._get({**base, "mode": "groups", "group_id": second.id, "search": "Formula"})
        self.assertEqual(groups.status_code, 200)
        group_rows = list(csv.reader(StringIO(self._csv(groups)[1])))
        self.assertIn(["Messages (All Time)", "1"], group_rows)
        self.assertIn([str(second.id), "'=Formula group", "1", "1", "1"], group_rows)
        self.assertNotIn([str(first.id), "First group", "1", "1", "1"], group_rows)

        users = self._get({**base, "mode": "users", "user_role": "Mentor"})
        self.assertEqual(users.status_code, 200)
        user_rows = list(csv.reader(StringIO(self._csv(users)[1])))
        self.assertIn(["Users with Messages", "1"], user_rows)
        self.assertIn([str(self.mentor.id), "Report Person", "Mentor", "'=Formula group", "1", "1"], user_rows)
        self.assertNotIn([str(self.student_granted.id), "Report Person", "Student", "First group", "1", "1"], user_rows)

        selected_users = self._get({**base, "mode": "users", "group_id": first.id})
        self.assertEqual(selected_users.status_code, 200)
        selected_rows = list(csv.reader(StringIO(self._csv(selected_users)[1])))
        self.assertIn([str(self.student_granted.id), "Report Person", "Student", "First group", "1", "1"], selected_rows)
        self.assertFalse(any(row and row[0] == str(self.mentor.id) for row in selected_rows))

    def test_messages_page_export_preserves_cross_year_range_and_all_time_details(self):
        first = Groups.objects.create(group_name="First group")
        second = Groups.objects.create(group_name="Second group")
        GroupMembership.objects.create(group=first, user=self.student_granted, membership_role="student")
        GroupMembership.objects.create(group=second, user=self.mentor, membership_role="mentor")
        for group, day in ((first, "2025-01-01"), (first, "2025-12-31"), (second, "2026-01-01")):
            Messages.objects.create(
                group=group, sender_user=self.student_granted, message_text="message",
                sent_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"),
            )
        params = {
            "report": "messages", "start_date": "2025-12-31", "end_date": "2026-01-01",
            "anchor_date": "2026-01-01", "interval": "day", "mode": "groups",
        }
        period = self._get(params)
        self.assertEqual(period.status_code, 200)
        self.assertIn('messages-analytics-groups-2026-01-01.csv', period["Content-Disposition"])
        period_rows = list(csv.reader(StringIO(self._csv(period)[1])))
        self.assertIn(["Trend Interval", "day"], period_rows)
        self.assertIn(["Messages (All Time)", "3"], period_rows)
        self.assertIn(["Messages This Period", "2"], period_rows)
        self.assertIn([str(first.id), "First group", "1", "0.5", "1"], period_rows)

        all_details = self._get({**params, "show_all_details": "true"})
        self.assertEqual(all_details.status_code, 200)
        all_rows = list(csv.reader(StringIO(self._csv(all_details)[1])))
        self.assertIn([str(first.id), "First group", "2", "0.01", "1"], all_rows)
        self.assertIn([str(second.id), "Second group", "1", "0", "1"], all_rows)

    def test_messages_user_export_scopes_all_counts_to_message_group_and_keeps_filters(self):
        first = Groups.objects.create(group_name="First group")
        second = Groups.objects.create(group_name="Second group")
        for user, name in ((self.student_granted, "Student Alpha"),
                           (self.student_not_granted, "Student Beta"),
                           (self.mentor, "Mentor Alpha")):
            user.first_name, user.last_name = name.split()
            user.save(update_fields=["first_name", "last_name"])
            GroupMembership.objects.create(group=first, user=user, membership_role="student")
            GroupMembership.objects.create(group=second, user=user, membership_role="student")

        def messages(group, user, day, count):
            Messages.objects.bulk_create([
                Messages(group=group, sender_user=user, message_text="message",
                         sent_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"))
                for _ in range(count)
            ])

        messages(first, self.student_granted, "2026-08-01", 4)
        messages(first, self.student_granted, "2026-09-08", 2)
        messages(first, self.student_granted, "2026-09-10", 1)
        messages(second, self.student_granted, "2026-09-10", 10)
        messages(first, self.student_not_granted, "2026-09-10", 2)
        messages(first, self.mentor, "2026-09-10", 3)
        # A deleted message must not contribute to any of the counts.
        Messages.objects.create(group=first, sender_user=self.student_granted,
                                sent_at=datetime.fromisoformat("2026-09-10T12:00:00+00:00"),
                                deleted_at=datetime.fromisoformat("2026-09-10T13:00:00+00:00"))
        params = {
            "report": "messages", "start_date": "2026-09-10", "end_date": "2026-09-10",
            "anchor_date": "2026-09-10", "mode": "users", "group_id": first.id,
            "user_role": "Student", "sort_by": "last7Days", "sort_order": "asc",
        }
        response = self._get(params)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(self._csv(response)[1])))
        header = rows.index(["User ID", "User", "Role", "Current Group(s)", "Messages", "Messages in Last 7 Observed Days"])
        self.assertEqual(rows[header + 1:], [
            [str(self.student_not_granted.id), "Student Beta", "Student", "First group, Second group", "2", "2"],
            [str(self.student_granted.id), "Student Alpha", "Student", "First group, Second group", "1", "3"],
        ])
        self.assertIn(["Messages (All Time)", "12"], rows)
        self.assertIn(["Messages This Period", "6"], rows)
        self.assertIn(["Users with Messages", "2"], rows)

        response = self._get({**params, "show_all_details": "true", "search": "Alpha"})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(self._csv(response)[1])))
        header = rows.index(["User ID", "User", "Role", "Current Group(s)", "Messages", "Messages in Last 7 Observed Days"])
        self.assertEqual(rows[header + 1:], [
            [str(self.student_granted.id), "Student Alpha", "Student", "First group, Second group", "7", "3"],
        ])
        self.assertIn(["Messages This Period", "6"], rows)

    def test_messages_group_export_all_time_keeps_selected_group_search_and_sort(self):
        first = Groups.objects.create(group_name="Selected Alpha")
        second = Groups.objects.create(group_name="Other Alpha")
        for group, day, count in ((first, "2026-08-01", 2), (first, "2026-09-10", 1),
                                  (second, "2026-09-10", 8)):
            Messages.objects.bulk_create([
                Messages(group=group, sender_user=self.student_granted, message_text="message",
                         sent_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"))
                for _ in range(count)
            ])
        params = {
            "report": "messages", "start_date": "2026-09-10", "end_date": "2026-09-10",
            "anchor_date": "2026-09-10", "mode": "groups", "group_id": first.id,
            "show_all_details": "true", "search": "Alpha", "sort_by": "value", "sort_order": "asc",
        }
        response = self._get(params)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(self._csv(response)[1])))
        header = rows.index(["Group ID", "Group", "Messages", "Average per Day", "Messages in Last 7 Observed Days"])
        self.assertEqual(rows[header + 1:], [[str(first.id), "Selected Alpha", "3", "0.07", "1"]])
        self.assertIn(["Messages (All Time)", "3"], rows)
        self.assertIn(["Messages This Period", "1"], rows)

        response = self._get({**params, "search": "Other"})
        rows = list(csv.reader(StringIO(self._csv(response)[1])))
        self.assertEqual(rows[header + 1:], [])

    def test_only_admins_can_export_reports(self):
        anonymous = self.client.get(self.url, {"report": "participants"})
        self.client.force_authenticate(user=self.non_admin)
        non_admin = self.client.get(self.url, {"report": "participants"})

        self.assertIn(
            anonymous.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(non_admin.status_code, status.HTTP_403_FORBIDDEN)

    def test_participants_filters_and_escapes_spreadsheet_formulas(self):
        response = self._get(
            {
                "report": "participants",
                "group_by": "interest",
                "country_id": self.au.id,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows, raw = self._csv(response)
        self.assertEqual(
            rows,
            [
                {"category": "'=Formula", "count": "1", "percentage": "50.00"},
                {"category": "Biology", "count": "1", "percentage": "50.00"},
            ],
        )
        self.assertTrue(raw.startswith("category,count,percentage\r\n"))
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("participants-", response["Content-Disposition"])

    def test_participants_status_filter_uses_current_account_status(self):
        response = self._get(
            {
                "report": "participants",
                "group_by": "status",
                "status": "pending",
            }
        )

        rows, _ = self._csv(response)
        self.assertEqual(
            rows,
            [{"category": "Pending", "count": "1", "percentage": "100.00"}],
        )

    def test_permission_report_groups_and_filters_without_personal_data(self):
        response = self._get(
            {
                "report": "permission",
                "group_by": "state",
                "country_id": self.au.id,
                "status": "active",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows, raw = self._csv(response)
        self.assertEqual(
            rows,
            [
                {
                    "region": "NSW",
                    "total_students": "1",
                    "permission_granted": "1",
                    "permission_not_granted": "0",
                    "permission_rate": "100.00",
                }
            ],
        )
        self.assertNotIn("email", raw.lower())
        self.assertNotIn("parent", raw.lower())

    def test_permission_report_can_return_one_overall_summary(self):
        response = self._get({"report": "permission", "group_by": "none"})

        rows, _ = self._csv(response)
        self.assertEqual(
            rows,
            [
                {
                    "region": "All",
                    "total_students": "2",
                    "permission_granted": "1",
                    "permission_not_granted": "1",
                    "permission_rate": "50.00",
                }
            ],
        )

    def test_login_activity_counts_events_and_unique_users_by_utc_day(self):
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    actor_user=self.student_granted,
                    entity_type="user",
                    entity_id=self.student_granted.id,
                    action=AuditLog.ActionChoices.LOGIN,
                    created_at=datetime(2026, 9, 1, 1, tzinfo=datetime_timezone.utc),
                ),
                AuditLog(
                    actor_user=self.student_granted,
                    entity_type="user",
                    entity_id=self.student_granted.id,
                    action=AuditLog.ActionChoices.LOGIN,
                    created_at=datetime(2026, 9, 1, 2, tzinfo=datetime_timezone.utc),
                ),
                AuditLog(
                    actor_user=self.student_not_granted,
                    entity_type="user",
                    entity_id=self.student_not_granted.id,
                    action=AuditLog.ActionChoices.LOGIN,
                    created_at=datetime(2026, 9, 1, 3, tzinfo=datetime_timezone.utc),
                ),
                AuditLog(
                    actor_user=self.mentor,
                    entity_type="user",
                    entity_id=self.mentor.id,
                    action=AuditLog.ActionChoices.LOGIN,
                    created_at=datetime(2026, 9, 2, 4, tzinfo=datetime_timezone.utc),
                ),
            ]
        )

        response = self._get(
            {
                "report": "login_activity",
                "start_date": "2026-09-01",
                "end_date": "2026-09-03",
                "country_id": self.au.id,
            }
        )

        rows, _ = self._csv(response)
        self.assertEqual(
            rows,
            [
                {
                    "period_start": "2026-09-01",
                    "period_end": "2026-09-02",
                    "login_count": "3",
                    "unique_logged_in_users": "2",
                },
                {
                    "period_start": "2026-09-02",
                    "period_end": "2026-09-03",
                    "login_count": "0",
                    "unique_logged_in_users": "0",
                },
                {
                    "period_start": "2026-09-03",
                    "period_end": "2026-09-04",
                    "login_count": "0",
                    "unique_logged_in_users": "0",
                },
            ],
        )

    def test_announcement_delivery_exports_only_summary_fields(self):
        announcement = Announcement.objects.create(
            author_user=self.admin,
            title="=Quarterly update",
            body="Private body",
        )
        AnnouncementDelivery.objects.create(
            announcement=announcement,
            initiated_by=self.admin,
            started_at=datetime(2026, 9, 1, 8, tzinfo=datetime_timezone.utc),
            completed_at=datetime(2026, 9, 1, 8, 5, tzinfo=datetime_timezone.utc),
            status=AnnouncementDelivery.Status.PARTIAL,
            recipient_count=5,
            success_count=4,
            failure_count=1,
            failed_recipients=[{"email": "private@example.com", "error": "x"}],
            error_summary="provider detail",
        )

        response = self._get(
            {
                "report": "announcement_delivery",
                "start_date": "2026-09-01",
                "end_date": "2026-09-01",
                "delivery_status": "partial",
            }
        )

        rows, raw = self._csv(response)
        self.assertEqual(
            rows,
            [
                {
                    "announcement_id": str(announcement.id),
                    "title": "'=Quarterly update",
                    "sent_at": "2026-09-01T08:05:00+00:00",
                    "success_count": "4",
                    "failure_count": "1",
                    "delivery_rate": "80.00",
                }
            ],
        )
        self.assertNotIn("private@example.com", raw)
        self.assertNotIn("provider detail", raw)

    def test_empty_reports_still_return_their_headers(self):
        expected_headers = {
            "participants": "category,count,percentage\r\n",
            "permission": (
                "region,total_students,permission_granted,"
                "permission_not_granted,permission_rate\r\n"
            ),
            "login_activity": (
                "period_start,period_end,login_count,unique_logged_in_users\r\n"
            ),
            "announcement_delivery": (
                "announcement_id,title,sent_at,success_count,failure_count,"
                "delivery_rate\r\n"
            ),
        }
        for report, header in expected_headers.items():
            with self.subTest(report=report):
                params = {
                    "report": report,
                    "start_date": "2000-01-01",
                    "end_date": "2000-01-01",
                }
                if report == "permission":
                    params["country_id"] = 999999
                    params.pop("start_date")
                    params.pop("end_date")
                response = self._get(params)
                _, raw = self._csv(response)
                if report == "login_activity":
                    self.assertIn(",0,0\r\n", raw)
                else:
                    self.assertEqual(raw, header)

    def test_invalid_or_incompatible_parameters_return_clear_bad_request(self):
        cases = [
            ({"report": "unknown"}, "report"),
            ({"report": "participants", "group_by": "planet"}, "group_by"),
            (
                {
                    "report": "login_activity",
                    "range": "7d",
                    "start_date": "2026-09-01",
                },
                "range",
            ),
            ({"report": "permission", "interest": "Biology"}, "interest"),
        ]
        for params, field in cases:
            with self.subTest(params=params):
                response = self._get(params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data["fields"])

    def test_login_activity_rejects_excessive_date_range(self):
        response = self._get({
            "report": "login_activity",
            "start_date": "0001-01-01",
            "end_date": "9999-12-31",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data["fields"])

    def test_login_activity_rejects_unrepresentable_period_end(self):
        response = self._get({
            "report": "login_activity",
            "start_date": "9999-12-31",
            "end_date": "9999-12-31",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data["fields"])

    def test_announcement_delivery_accepts_last_calendar_day(self):
        response = self._get({
            "report": "announcement_delivery",
            "start_date": "9999-12-31",
            "end_date": "9999-12-31",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._csv(response)
