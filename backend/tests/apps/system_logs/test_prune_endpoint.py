from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.system_logs.models import SystemLogEntry
from apps.users.models import AdminScope

from ._factory import make_entry

URL = "/api/v1/admin/system-logs/prune/"
HEADER = "HTTP_X_EMAIL_JOBS_TOKEN"


@override_settings(EMAIL_JOBS_TOKEN="jobs-secret", RSVP_REMINDER_TOKEN="", SYSTEM_LOG_RETENTION_DAYS=30)
class PruneEndpointTests(APITestCase):
    def test_deletes_rows_past_retention_with_the_jobs_token(self):
        make_entry(age=timedelta(days=31))
        kept = make_entry(age=timedelta(days=1))

        response = self.client.post(URL, **{HEADER: "jobs-secret"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"deleted": 1})
        self.assertEqual(list(SystemLogEntry.objects.values_list("id", flat=True)), [kept.id])

    def test_wrong_or_missing_token_is_refused_and_deletes_nothing(self):
        make_entry(age=timedelta(days=31))

        self.assertEqual(self.client.post(URL, **{HEADER: "wrong"}).status_code, 401)
        self.assertEqual(self.client.post(URL).status_code, 401)
        self.assertEqual(SystemLogEntry.objects.count(), 1)

    def test_a_signed_in_admin_still_needs_the_token(self):
        admin = get_user_model().objects.create_user(email="prune.admin@example.com", password="pass123")
        AdminScope.objects.create(user=admin)
        self.client.force_login(admin)

        self.assertEqual(self.client.post(URL).status_code, 401)

    @override_settings(EMAIL_JOBS_TOKEN="")
    def test_unconfigured_token_answers_503(self):
        self.assertEqual(self.client.post(URL, **{HEADER: ""}).status_code, 503)

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(URL, **{HEADER: "jobs-secret"}).status_code, 405)
