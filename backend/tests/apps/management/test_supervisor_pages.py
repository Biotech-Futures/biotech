"""Management's Supervisor Pages Visibility switch: the pages off by default;
readable by anyone signed in, changed by admins only."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import AdminScope, User

URL = "/api/v1/management/supervisor-pages/"


class SupervisorPagesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin-pages@test.com", password="pw12345!")
        AdminScope.objects.create(user=self.admin)
        self.supervisor = User.objects.create_user(email="sup-pages@test.com", password="pw12345!")

    def test_off_until_an_admin_turns_it_on(self):
        self.client.force_authenticate(self.supervisor)
        self.assertEqual(self.client.get(URL).json(), {"shown": False})

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {"shown": True}, format="json").json(), {"shown": True})

        self.client.force_authenticate(self.supervisor)
        self.assertEqual(self.client.get(URL).json(), {"shown": True})

    def test_only_admins_change_it(self):
        self.client.force_authenticate(self.supervisor)
        self.assertEqual(self.client.put(URL, {"shown": True}, format="json").status_code, 403)

    def test_needs_true_or_false(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {"shown": "yes"}, format="json").status_code, 400)
        self.assertEqual(self.client.put(URL, {}, format="json").status_code, 400)

    def test_needs_signing_in(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))
