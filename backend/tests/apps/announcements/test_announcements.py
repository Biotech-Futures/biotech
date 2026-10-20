"""The platform's announcements, as readers see them.

An announcement body may greet its reader by name (``{{ first_name }}``).
The tags are filled with the reading user's own details when the announcement
is served on the platform — unlike the admin dashboard, which reads the body
as written so it stays editable, and unlike its email, which fills each
recipient's.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.announcement import get_announcement_by_id
from apps.announcements.models import Announcement
from apps.announcements.rendering import body_to_html, fill_merge_tags
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope

LIST_URL = "/announcements/v1/"


class AnnouncementMergeTagFillTests(TestCase):
    """Reading an announcement on the platform fills its merge tags."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="author@example.com",
            password="testpass",
            first_name="An",
            last_name="Author",
        )
        self.reader = User.objects.create_user(
            email="ada@example.com",
            password="testpass",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.announcement = Announcement.objects.create(
            author_user=self.author,
            title="Welcome",
            body=(
                "<p>Hi {{ first_name }}, welcome to the team, "
                "{{ unknown_tag }}.</p>"
            ),
            visibility_scope=Announcement.VisibilityScope.GLOBAL,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.reader)

    def test_detail_fills_the_reader_s_own_name(self):
        response = self.client.get(f"{LIST_URL}{self.announcement.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()["body"]
        self.assertIn("Hi Ada,", body)
        self.assertNotIn("{{ first_name }}", body)
        # A tag the announcement doesn't know is left exactly as written.
        self.assertIn("{{ unknown_tag }}", body)

    def test_list_fills_the_reader_s_own_name(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()
        items = results["results"] if isinstance(results, dict) else results
        row = next(item for item in items if item["id"] == self.announcement.id)
        self.assertIn("Hi Ada,", row["body"])
        self.assertNotIn("{{ first_name }}", row["body"])

    def test_a_full_name_is_available_too(self):
        self.announcement.body = "<p>Dear {{ name }} ({{ email }})</p>"
        self.announcement.save(update_fields=["body"])

        response = self.client.get(f"{LIST_URL}{self.announcement.id}/")
        body = response.json()["body"]
        self.assertIn("Dear Ada Lovelace (ada@example.com)", body)

    def test_admin_api_keeps_the_tags_for_editing(self):
        # The composer reads through the admin service, which must keep the
        # body exactly as written or the tags would be lost on the next save.
        row = get_announcement_by_id(self.announcement.id)
        self.assertIn("{{ first_name }}", row["data"]["body"])


class AnnouncementMergeTagReferenceTests(TestCase):
    """The composer's tag reference."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            first_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_merge_tags_endpoint_lists_the_available_tags(self):
        response = self.client.get("/api/v1/admin/announcement/merge-tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [tag["name"] for tag in response.json()["data"]]
        self.assertIn("first_name", names)
        self.assertIn("name", names)

    def test_merge_tags_endpoint_requires_an_admin(self):
        student = User.objects.create_user(email="s@example.com", password="x")
        client = APIClient()
        client.force_authenticate(student)
        response = client.get("/api/v1/admin/announcement/merge-tags/")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class AnnouncementRenderingTests(TestCase):
    """``body_to_html`` gives a plain-text body the same shape the portal does."""

    def test_html_is_kept_as_written(self):
        html = "<p>Already <strong>HTML</strong>.</p>"
        self.assertEqual(body_to_html(html), html)

    def test_plain_text_gets_paragraphs_and_line_breaks(self):
        rendered = body_to_html("First line\nSecond line\n\nSecond paragraph")
        self.assertEqual(
            rendered,
            "<p>First line<br>Second line</p><p>Second paragraph</p>",
        )

    def test_plain_text_is_escaped(self):
        rendered = body_to_html("5 < 6 & 7 > 4")
        self.assertEqual(rendered, "<p>5 &lt; 6 &amp; 7 &gt; 4</p>")

    def test_html_like_text_is_kept_for_the_sanitiser(self):
        rendered = body_to_html("<script>alert(1)</script>")
        # Looks like HTML, so it is kept as written and left to the sanitiser.
        self.assertIn("<script>", rendered)

    def test_fill_leaves_other_tags_alone(self):
        user = User.objects.create_user(
            email="u@example.com", password="x", first_name="Sam",
        )
        self.assertEqual(
            fill_merge_tags("Hi {{ first_name }} {{ nope }}", user),
            "Hi Sam {{ nope }}",
        )
