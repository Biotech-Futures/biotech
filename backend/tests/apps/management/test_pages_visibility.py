"""Pages Visibility kept by the server (apps.management.pages_visibility):
until its date, students, mentors and supervisors are refused the APIs behind
Home, Groups, Events, Announcements and Resources. Admins always get them, and
everything else (a country list, My Groups) stays open. Signed in with a
session, as the site is, since that's who the middleware sees."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.management.models import SupervisorPagesSetting
from apps.users.models import AdminScope, SupervisorProfile, User

# One of each page's: Home, Groups, Events, Announcements, Resources, and
# Home's and Groups' tasks.
HIDDEN_URLS = (
    "/dashboard/v1/progress/",
    "/groups/groups/?mine=true",
    "/events/v1/",
    "/announcements/v1/",
    "/resources/resource-types/",
    "/api/v1/tasks/",
    "/api/v1/tasks/role-tasks/mine/",
)


def _signed_in(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def _person(email):
    user = User.objects.create_user(email=email, password="pw12345!", first_name="Sam", last_name="Lee")
    user.activate()
    return user


def _show_from(moment):
    SupervisorPagesSetting.objects.update_or_create(pk=1, defaults={"shown_from": moment})


class PagesVisibilityTests(TestCase):
    def setUp(self):
        self.supervisor = _person("sam@school.example")
        SupervisorProfile.objects.create(user=self.supervisor, school_name="Example High")
        self.admin = _person("ada@example.com")
        AdminScope.objects.create(user=self.admin)

    def assert_hidden(self, client, url):
        response = client.get(url)
        self.assertEqual(response.status_code, 403, url)
        self.assertEqual(response.json()["code"], "pages_hidden", url)

    def test_hidden_until_a_date_is_set(self):
        client = _signed_in(self.supervisor)
        for url in HIDDEN_URLS:
            with self.subTest(url=url):
                self.assert_hidden(client, url)

    def test_hidden_until_the_date_comes_then_open(self):
        client = _signed_in(self.supervisor)
        _show_from(timezone.now() + timedelta(days=1))
        self.assert_hidden(client, "/events/v1/")

        _show_from(timezone.now() - timedelta(minutes=1))
        for url in HIDDEN_URLS:
            with self.subTest(url=url):
                self.assertNotEqual(client.get(url).status_code, 403, url)

    def test_never_hidden_from_admins(self):
        client = _signed_in(self.admin)
        for url in HIDDEN_URLS:
            with self.subTest(url=url):
                self.assertNotEqual(client.get(url).status_code, 403, url)

    def test_the_rest_stays_open(self):
        client = _signed_in(self.supervisor)
        # Registration's and the profile's country list, and the supervisor's My Groups.
        for url in ("/api/v1/groups/countries/", "/api/v1/users/supervised-groups/"):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200, url)

    def test_someone_not_signed_in_is_left_to_the_page(self):
        # Each page answers them as before: the public events list, say.
        for url in HIDDEN_URLS:
            with self.subTest(url=url):
                response = APIClient().get(url)
                self.assertNotEqual(response.json().get("code"), "pages_hidden", url)


class FirstDateTests(TestCase):
    """The date management.0023 sets once, so the pages don't vanish for
    everyone on the deploy that starts keeping them back."""

    def run_migration(self):
        from importlib import import_module

        from django.apps import apps

        import_module("apps.management.migrations.0023_pages_visibility_default").default_shown_from(apps, None)
        return SupervisorPagesSetting.load().shown_from

    def test_this_years_challenge_start(self):
        from apps.management.models import ChallengeStart
        from apps.submissions.services import current_cohort

        starts_at = timezone.now() - timedelta(days=90)
        ChallengeStart.objects.create(year=current_cohort(), starts_at=starts_at)
        self.assertEqual(self.run_migration(), starts_at)

    def test_the_moment_its_deployed_without_one(self):
        before = timezone.now()
        shown_from = self.run_migration()
        self.assertGreaterEqual(shown_from, before)
        self.assertLessEqual(shown_from, timezone.now())

    def test_a_date_already_set_stays(self):
        chosen = timezone.now() + timedelta(days=30)
        _show_from(chosen)
        self.assertEqual(self.run_migration(), chosen)
