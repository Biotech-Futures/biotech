import csv
import io
import json
import logging
from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest import mock

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.system_logs import export
from apps.system_logs.models import SystemLogEntry
from apps.users.models import AdminScope

from ._factory import make_entry

User = get_user_model()

LIST_URL = "/api/v1/admin/system-logs/"
EXPORT_URL = "/api/v1/admin/system-logs/export/"


def _detail_url(entry):
    return f"/api/v1/admin/system-logs/{entry.pk}/"


class _AdminApiTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="logs.admin@example.com", password="pass123")
        AdminScope.objects.create(user=self.admin)
        self.member = User.objects.create_user(email="member@example.com", password="pass123")
        self.client.force_authenticate(user=self.admin)


class PermissionTests(_AdminApiTestCase):
    def test_every_endpoint_refuses_non_admins_and_anonymous_users(self):
        entry = make_entry()
        for url in (LIST_URL, _detail_url(entry), EXPORT_URL):
            with self.subTest(url=url):
                self.client.force_authenticate(user=self.member)
                self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

                self.client.force_authenticate(user=None)
                self.assertIn(self.client.get(url).status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_admins_can_use_every_endpoint(self):
        entry = make_entry()
        for url in (LIST_URL, _detail_url(entry), EXPORT_URL):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_non_admin_export_writes_no_audit_row(self):
        self.client.force_authenticate(user=self.member)
        self.client.get(EXPORT_URL)
        self.assertFalse(AuditLog.objects.exists())


class ListTests(_AdminApiTestCase):
    def test_lists_newest_first_with_a_preview_of_long_messages(self):
        older = make_entry(age=timedelta(hours=2), message="older")
        newer = make_entry(message="x" * 1000, traceback="Traceback...", user=self.member, request_id="rid-1")

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        first, second = response.data["results"]
        self.assertEqual([first["id"], second["id"]], [newer.id, older.id])
        self.assertEqual(len(first["message"]), 300)
        self.assertTrue(first["message_truncated"])
        self.assertTrue(first["has_traceback"])
        self.assertNotIn("traceback", first)
        self.assertEqual(first["user"]["email"], self.member.email)
        self.assertFalse(second["message_truncated"])
        self.assertFalse(second["has_traceback"])
        self.assertIsNone(second["user"])

    def test_paginates_with_a_capped_page_size(self):
        for _ in range(5):
            make_entry()

        page = self.client.get(LIST_URL, {"page_size": 2, "page": 2}).data
        self.assertEqual((page["count"], len(page["results"])), (5, 2))

        with mock.patch("apps.system_logs.views.SystemLogPagination.max_page_size", 3):
            self.assertEqual(len(self.client.get(LIST_URL, {"page_size": 100}).data["results"]), 3)

    def test_rows_of_a_deleted_user_still_list(self):
        make_entry(user=self.member)
        self.member.delete()

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["results"][0]["user"])


class FilterTests(_AdminApiTestCase):
    def _ids(self, **params):
        response = self.client.get(LIST_URL, params)
        self.assertEqual(response.status_code, 200, response.data)
        return {row["id"] for row in response.data["results"]}

    def test_level_is_a_minimum_by_name_or_number(self):
        info = make_entry(level=logging.INFO)
        warning = make_entry(level=logging.WARNING)
        error = make_entry(level=logging.ERROR)

        self.assertEqual(self._ids(level="warning"), {warning.id, error.id})
        self.assertEqual(self._ids(level="40"), {error.id})
        self.assertEqual(self._ids(level="INFO"), {info.id, warning.id, error.id})

    def test_source_matches_the_start_of_the_logger_name(self):
        mailer = make_entry(logger_name="apps.services.mailer")
        views = make_entry(logger_name="apps.services.views")
        make_entry(logger_name="django.request")

        self.assertEqual(self._ids(source="apps.services"), {mailer.id, views.id})

    def test_user_by_id_or_part_of_the_email(self):
        mine = make_entry(user=self.member)
        make_entry(user=self.admin)
        make_entry()

        self.assertEqual(self._ids(user=str(self.member.id)), {mine.id})
        self.assertEqual(self._ids(user="MEMBER@"), {mine.id})

    def test_text_search_in_the_message(self):
        hit = make_entry(message="SMTP connection refused")
        make_entry(message="all good")

        self.assertEqual(self._ids(q="connection REFUSED"), {hit.id})

    def test_request_id_is_exact(self):
        hit = make_entry(request_id="abc123")
        make_entry(request_id="abc1234")

        self.assertEqual(self._ids(request_id="abc123"), {hit.id})

    def test_date_range_with_dates_includes_the_whole_to_day(self):
        # Noon on fixed days, so the test doesn't depend on the time it runs.
        today = timezone.now().astimezone(dt_timezone.utc).date()
        noon = datetime.combine(today, time(12), tzinfo=dt_timezone.utc)
        make_entry(at=noon - timedelta(days=10))
        middle = make_entry(at=noon - timedelta(days=5))
        latest = make_entry(at=noon)

        from_day = (today - timedelta(days=6)).isoformat()
        self.assertEqual(self._ids(**{"from": from_day}), {middle.id, latest.id})
        to_day = (today - timedelta(days=5)).isoformat()
        self.assertEqual(self._ids(**{"from": from_day, "to": to_day}), {middle.id})

    def test_date_range_with_datetimes_and_offsets(self):
        entry = make_entry(age=timedelta(hours=1))
        moment = entry.created_at

        self.assertEqual(self._ids(**{"from": moment.isoformat(), "to": moment.isoformat()}), {entry.id})
        later = (moment + timedelta(minutes=1)).astimezone(dt_timezone(timedelta(hours=10))).isoformat()
        self.assertEqual(self._ids(**{"from": later}), set())

    def test_a_local_day_sent_as_offset_datetimes_selects_exactly_that_day(self):
        # What the admin page sends for "15 Oct" in Sydney (AEDT, +11:00):
        # start of the local day for from, its last millisecond for to.
        utc = dt_timezone.utc
        make_entry(at=datetime(2026, 10, 14, 12, 59, 59, tzinfo=utc))  # 14 Oct 23:59:59 local
        first = make_entry(at=datetime(2026, 10, 14, 13, 0, tzinfo=utc))  # 15 Oct 00:00 local
        last = make_entry(at=datetime(2026, 10, 15, 12, 59, 59, 999000, tzinfo=utc))  # 15 Oct 23:59:59.999 local
        make_entry(at=datetime(2026, 10, 15, 13, 0, tzinfo=utc))  # 16 Oct 00:00 local

        ids = self._ids(**{"from": "2026-10-15T00:00:00.000+11:00", "to": "2026-10-15T23:59:59.999+11:00"})

        self.assertEqual(ids, {first.id, last.id})

    def test_each_end_keeps_its_own_offset_across_a_daylight_saving_change(self):
        # Sydney moves from +10:00 to +11:00 on 4 Oct 2026, so a range across
        # it has a different offset at each end.
        utc = dt_timezone.utc
        make_entry(at=datetime(2026, 9, 30, 13, 59, tzinfo=utc))  # 30 Sep 23:59 local (+10)
        inside = make_entry(at=datetime(2026, 9, 30, 14, 0, tzinfo=utc))  # 1 Oct 00:00 local (+10)
        make_entry(at=datetime(2026, 10, 15, 13, 0, tzinfo=utc))  # 16 Oct 00:00 local (+11)

        ids = self._ids(**{"from": "2026-10-01T00:00:00.000+10:00", "to": "2026-10-15T23:59:59.999+11:00"})

        self.assertEqual(ids, {inside.id})

    def test_offset_plus_sign_must_be_url_encoded(self):
        # URLSearchParams (buildAdminQuery) sends "+" as %2B. A raw "+" in a
        # query string means a space, which is refused rather than misread.
        make_entry(at=datetime(2026, 10, 15, 1, 0, tzinfo=dt_timezone.utc))

        encoded = self.client.get(f"{LIST_URL}?from=2026-10-15T00:00:00.000%2B11:00")
        raw = self.client.get(f"{LIST_URL}?from=2026-10-15T00:00:00.000+11:00")

        self.assertEqual(encoded.status_code, 200)
        self.assertEqual(encoded.data["count"], 1)
        self.assertEqual(raw.status_code, 400)
        self.assertIn("from", raw.data["fields"])

    def test_utc_z_suffix_is_accepted(self):
        hit = make_entry(at=datetime(2026, 10, 15, 13, 0, tzinfo=dt_timezone.utc))

        self.assertEqual(self._ids(**{"from": "2026-10-15T13:00:00Z", "to": "2026-10-15T13:00:00Z"}), {hit.id})

    def test_filters_combine(self):
        hit = make_entry(level=logging.ERROR, logger_name="apps.services.mailer", message="send failed")
        make_entry(level=logging.WARNING, logger_name="apps.services.mailer", message="send failed")
        make_entry(level=logging.ERROR, logger_name="django.request", message="send failed")

        self.assertEqual(self._ids(level="ERROR", source="apps.services", q="failed"), {hit.id})

    def test_bad_values_are_a_400_naming_the_filter(self):
        response = self.client.get(LIST_URL, {"level": "LOUD", "from": "yesterday"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("level", response.data["fields"])
        self.assertIn("from", response.data["fields"])


class DetailTests(_AdminApiTestCase):
    def test_returns_the_full_row(self):
        entry = make_entry(message="m" * 1000, traceback="Traceback (most recent call last): ...", extra={"reason": "x"})

        data = self.client.get(_detail_url(entry)).data

        self.assertEqual(len(data["message"]), 1000)
        self.assertEqual(data["traceback"], entry.traceback)
        self.assertEqual(data["extra"], {"reason": "x"})

    def test_missing_row_is_404(self):
        self.assertEqual(self.client.get("/api/v1/admin/system-logs/999999/").status_code, 404)


class ExportTests(_AdminApiTestCase):
    def _download(self, **params):
        response = self.client.get(EXPORT_URL, params)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        return response, b"".join(response.streaming_content).decode("utf-8")

    def test_csv_has_a_header_and_one_line_per_row(self):
        make_entry(message="first", user=self.member, request_id="rid-9", request_path="/api/v1/x/")

        response, body = self._download()

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertRegex(response["Content-Disposition"], r'attachment; filename="system-logs-\d{8}-\d{6}\.csv"')
        rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
        self.assertEqual(rows[0][:4], ["Time (UTC)", "Level", "Source", "Message"])
        self.assertEqual(len(rows), 2)
        record = dict(zip(rows[0], rows[1]))
        self.assertEqual(record["Message"], "first")
        self.assertEqual(record["User email"], self.member.email)
        self.assertEqual(record["Request ID"], "rid-9")

    def test_csv_cells_cannot_run_as_spreadsheet_formulas(self):
        make_entry(message='=HYPERLINK("http://evil.example","click")')

        _, body = self._download()

        self.assertIn("'=HYPERLINK", body)

    def test_export_uses_the_same_filters_as_the_list(self):
        make_entry(level=logging.ERROR, message="kept")
        make_entry(level=logging.WARNING, message="filtered out")

        _, body = self._download(level="ERROR")

        self.assertIn("kept", body)
        self.assertNotIn("filtered out", body)

    def test_json_is_one_object_per_line(self):
        make_entry(message="one")
        make_entry(message="two")

        response, body = self._download(type="json")

        self.assertTrue(response["Content-Type"].startswith("application/x-ndjson"))
        self.assertTrue(response["Content-Disposition"].endswith('.jsonl"'))
        messages = [json.loads(line)["message"] for line in body.splitlines()]
        self.assertEqual(messages, ["two", "one"])

    def test_stops_at_the_row_limit(self):
        for _ in range(3):
            make_entry()

        with mock.patch.object(export, "EXPORT_MAX_ROWS", 2):
            _, body = self._download(type="json")

        self.assertEqual(len(body.splitlines()), 2)

    def test_bad_type_or_filter_is_a_400(self):
        self.assertEqual(self.client.get(EXPORT_URL, {"type": "xml"}).status_code, 400)
        self.assertEqual(self.client.get(EXPORT_URL, {"level": "LOUD"}).status_code, 400)

    def test_records_who_exported_what(self):
        self._download(type="json", level="ERROR")

        audit = AuditLog.objects.get(action=AuditLog.ActionChoices.EXPORT)
        self.assertEqual(audit.actor_user, self.admin)
        self.assertEqual(audit.entity_type, "system_log")
        self.assertEqual(audit.after_state, {"type": "json", "filters": {"level": "ERROR"}})


class AsyncStreamingTests(_AdminApiTestCase):
    def test_asgi_requests_get_an_async_stream_of_the_same_lines(self):
        make_entry(message="streamed")

        from django.core.handlers.asgi import ASGIRequest

        request = mock.Mock(spec=ASGIRequest)
        content = export.streaming_content(request, export.json_lines(SystemLogEntry.objects.all()))
        self.assertTrue(hasattr(content, "__aiter__"))

        async def collect():
            return "".join([chunk async for chunk in content])

        body = async_to_sync(collect)()
        self.assertEqual(json.loads(body)["message"], "streamed")

    def test_wsgi_requests_get_the_plain_generator(self):
        lines = iter(["a\n"])
        self.assertIs(export.streaming_content(mock.Mock(), lines), lines)
