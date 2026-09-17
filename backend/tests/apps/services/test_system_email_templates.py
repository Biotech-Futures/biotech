"""
Every system email's default template exists and renders inside the branded layout.
Run with: python manage.py test tests.apps.services.test_system_email_templates
"""

from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase

from apps.services.email_branding import brand_context
from apps.services.email_registry import EMAIL_TYPES, get_email_type


def sample_context(key):
    """The registry's sample values, keyed the way the template reads them."""
    email_type = get_email_type(key)
    return {
        **brand_context(),
        **{tag.context_key: tag.sample for tag in email_type.merge_tags},
    }


class DefaultTemplateTests(SimpleTestCase):
    def test_every_default_template_exists(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                get_template(email_type.default_template)

    def test_every_default_template_renders_with_brand_chrome(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                html = render_to_string(email_type.default_template, sample_context(email_type.key))
                self.assertIn("BIOTech Futures", html)
                self.assertIn("cid:btf-logo", html)
                self.assertIn("biotechfutures.org", html)


class EventPromotionTemplateTests(SimpleTestCase):
    def test_shows_event_details_and_original_wording(self):
        html = render_to_string("emails/event_promotion.html", sample_context("event_promotion"))
        self.assertIn("Hi Alex,", html)
        self.assertIn("moved from the waitlist to confirmed for BIOTech Symposium", html)
        self.assertIn("Friday, 18 September 2026 at 10:00 AM AEST", html)
        self.assertIn("https://zoom.us/j/123456789", html)
        self.assertIn("Room 201, Science Building", html)
        self.assertIn("See you there!", html)

    def test_omits_join_and_location_rows_when_missing(self):
        context = sample_context("event_promotion")
        context["EVENT_JOIN_LINK"] = ""
        context["EVENT_LOCATION_TEXT"] = ""
        html = render_to_string("emails/event_promotion.html", context)
        self.assertNotIn(">\n                          Join\n", html)
        self.assertNotIn(">\n                          Where\n", html)

    def test_falls_back_to_there_without_a_first_name(self):
        context = sample_context("event_promotion")
        context["First_Name"] = ""
        self.assertIn("Hi there,", render_to_string("emails/event_promotion.html", context))


class FinalistTemplateTests(SimpleTestCase):
    def test_shows_group_name_and_original_wording(self):
        html = render_to_string("emails/finalist_notification.html", sample_context("finalist_notification"))
        self.assertIn("Your group (CRISPR Research 01) has been selected as a finalist", html)
        self.assertIn("will be in touch with details about presenting at the symposium", html)

    def test_escapes_group_name(self):
        context = sample_context("finalist_notification")
        context["GROUP_NAME"] = "<script>alert(1)</script>"
        html = render_to_string("emails/finalist_notification.html", context)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
