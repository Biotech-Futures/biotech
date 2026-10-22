"""Whether Azure's Always On is keeping the backend awake
(apps.services.always_on): its calls noted, and the status System Emails shows."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.services import always_on
from apps.services.models import SystemEmailSettings
from apps.users.models import AdminScope

User = get_user_model()
ON_AZURE = patch.dict("os.environ", {"WEBSITE_SITE_NAME": "biotechbe"})


def settings_row():
    return SystemEmailSettings.get()


class NotingTests(TestCase):
    def setUp(self):
        always_on._last_written = None

    def test_a_call_from_always_on_is_noted_whatever_its_address(self):
        self.client.get("/", HTTP_USER_AGENT="AlwaysOn")

        self.assertIsNotNone(settings_row().always_on_seen_at)

    def test_other_requests_are_not(self):
        self.client.get("/", HTTP_USER_AGENT="Mozilla/5.0")

        self.assertIsNone(settings_row().always_on_seen_at)

    def test_it_writes_at_most_once_a_minute(self):
        now = timezone.now()
        always_on.note_ping(now)
        first = settings_row().always_on_seen_at

        always_on.note_ping(now + timedelta(seconds=30))
        self.assertEqual(settings_row().always_on_seen_at, first)

        always_on.note_ping(now + timedelta(minutes=2))
        self.assertGreater(settings_row().always_on_seen_at, first)


class StateTests(TestCase):
    def test_nothing_to_tell_off_azure(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            env.pop("WEBSITE_SITE_NAME", None)
            self.assertEqual(always_on.always_on_state(), {"state": "not_azure", "lastSeenAt": None})

    @ON_AZURE
    def test_on_while_azure_keeps_calling(self):
        row = settings_row()
        row.always_on_seen_at = timezone.now() - timedelta(minutes=4)
        row.save()

        self.assertEqual(always_on.always_on_state()["state"], "on")

    @ON_AZURE
    def test_off_once_the_calls_stop(self):
        row = settings_row()
        row.always_on_seen_at = timezone.now() - timedelta(minutes=30)
        row.save()

        state = always_on.always_on_state()

        self.assertEqual(state["state"], "off")
        self.assertIsNotNone(state["lastSeenAt"])

    @ON_AZURE
    def test_checking_at_first_then_off_with_no_call(self):
        now = timezone.now()
        self.assertEqual(always_on.always_on_state(now)["state"], "checking")
        self.assertEqual(always_on.always_on_state(now + timedelta(minutes=10))["state"], "checking")

        self.assertEqual(always_on.always_on_state(now + timedelta(minutes=21))["state"], "off")


class EndpointTests(TestCase):
    url = "/api/v1/admin/email-settings/always-on/"

    def test_admins_see_it(self):
        admin = User.objects.create_user(email="ops.admin@example.com")
        AdminScope.objects.create(user=admin)
        client = APIClient()
        client.force_authenticate(admin)

        with ON_AZURE:
            response = client.get(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(response.json()["data"]["state"], {"checking", "on", "off"})

    def test_others_dont(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(email="someone@example.com"))

        self.assertEqual(client.get(self.url).status_code, 403)
