import html
import re
from urllib.parse import urlparse

from django.test import TestCase, override_settings

from apps.admin.services.analytics import get_email_delivery_analytics
from apps.services.models import EmailEngagementEvent, EmailEngagementTracker
from apps.services.system_email import RenderedEmail, build_message


@override_settings(BACKEND_URL="https://api.example.test")
class EmailTrackingTests(TestCase):
    def _message(self):
        return build_message(
            RenderedEmail(
                subject="Programme update",
                html='<html><body><a href="https://example.org/news?a=1&amp;b=2">News</a></body></html>',
                text="News: https://example.org/news?a=1&b=2",
            ),
            "reader@example.com",
            tracking_key="announcement",
        )

    def _html(self, message):
        return next(body for body, mimetype in message.alternatives if mimetype == "text/html")

    def test_build_message_adds_opaque_pixel_and_signed_click_link(self):
        message = self._message()
        tracker = EmailEngagementTracker.objects.get()
        body = self._html(message)

        self.assertIn(str(tracker.token), body)
        self.assertIn("/api/v1/services/email/track/open/", body)
        self.assertIn("/api/v1/services/email/track/click/", body)
        self.assertIn("Email engagement notice", body)
        self.assertIn(
            "https://www.biotechfutures.org/s/Privacy_Policy.pdf",
            body,
        )
        self.assertNotIn("reader@example.com", body)
        self.assertEqual(tracker.email_type, "announcement")
        self.assertEqual(tracker.recipient_email, "reader@example.com")
        self.assertEqual(message.body, "News: https://example.org/news?a=1&b=2")

    def test_open_endpoint_records_events_but_analytics_counts_unique_message(self):
        message = self._message()
        tracker = EmailEngagementTracker.objects.get()
        path = f"/api/v1/services/email/track/open/{tracker.token}.gif"

        first = self.client.get(path)
        second = self.client.get(path)
        tracker.refresh_from_db()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first["Content-Type"], "image/gif")
        self.assertIn("no-store", first["Cache-Control"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(tracker.open_count, 2)
        self.assertIsNotNone(tracker.first_opened_at)
        self.assertEqual(
            tracker.events.filter(event_type=EmailEngagementEvent.EventType.OPEN).count(),
            2,
        )
        self.assertEqual(get_email_delivery_analytics()["engagement"]["opened"], 1)

    def test_click_endpoint_records_event_and_redirects_to_signed_destination(self):
        message = self._message()
        body = self._html(message)
        tracked_href = html.unescape(re.search(r'href="([^"]+)"', body).group(1))
        response = self.client.get(urlparse(tracked_href).path)
        tracker = EmailEngagementTracker.objects.get()
        tracker.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.org/news?a=1&b=2")
        self.assertEqual(tracker.click_count, 1)
        self.assertIsNotNone(tracker.first_clicked_at)
        self.assertEqual(get_email_delivery_analytics()["engagement"]["clicked"], 1)

    def test_tampered_click_link_is_rejected(self):
        message = self._message()
        body = self._html(message)
        tracked_href = html.unescape(re.search(r'href="([^"]+)"', body).group(1))
        path = urlparse(tracked_href).path

        response = self.client.get(path.replace("/email/track/click/", "/email/track/click/x", 1))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(EmailEngagementEvent.objects.count(), 0)

    def test_non_web_links_are_not_rewritten(self):
        message = build_message(
            RenderedEmail(
                subject="Contact",
                html='<a href="mailto:hello@example.org">Email us</a><a href="#top">Top</a>',
                text="Contact",
            ),
            "reader@example.com",
            tracking_key="contact",
        )
        body = self._html(message)

        self.assertIn('href="mailto:hello@example.org"', body)
        self.assertIn('href="#top"', body)

    def test_outlook_vml_button_links_are_rewritten_too(self):
        message = build_message(
            RenderedEmail(
                subject="Open the portal",
                html=(
                    '<v:roundrect href="https://example.org/portal"></v:roundrect>'
                    '<a class="cta-link" href="https://example.org/portal">Open</a>'
                ),
                text="Open https://example.org/portal",
            ),
            "reader@example.com",
            tracking_key="portal",
        )
        body = self._html(message)
        hrefs = [html.unescape(value) for value in re.findall(r'href="([^"]+)"', body)]

        self.assertGreaterEqual(len(hrefs), 2)
        for href in hrefs[:2]:
            self.assertIn("/api/v1/services/email/track/click/", href)
            response = self.client.get(urlparse(href).path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "https://example.org/portal")

