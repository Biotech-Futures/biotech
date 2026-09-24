"""
The shared system email path: toggles, merge tags, rendering and sending.
Run with: python manage.py test tests.apps.services.test_system_email
"""

from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.core import mail
from django.db import DatabaseError
from django.test import TestCase, override_settings

from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.services.system_email import (
    FAILED,
    SENT,
    SKIPPED,
    fill_tags,
    html_to_text,
    is_email_enabled,
    render_system_email,
    send_system_email,
)

RESET_CONTEXT = {
    "First_Name": "Alex",
    "RESET_PASSWORD_LINK": "https://example.test/reset?token=abc",
    "EXPIRY_MINUTES": 30,
}


def disable_globally():
    SystemEmailSettings.objects.create(emails_enabled=False)


class ToggleTests(TestCase):
    def test_enabled_when_nothing_is_saved(self):
        self.assertTrue(is_email_enabled("password_reset"))

    def test_checking_a_toggle_never_creates_the_settings_row(self):
        is_email_enabled("password_reset")
        self.assertFalse(SystemEmailSettings.objects.exists())

    def test_type_switched_off(self):
        SystemEmailTemplate.objects.create(key="announcement", is_enabled=False)
        self.assertFalse(is_email_enabled("announcement"))
        self.assertTrue(is_email_enabled("submission_reminder"))

    def test_global_switch_off_disables_unlocked_types(self):
        disable_globally()
        self.assertFalse(is_email_enabled("announcement"))
        self.assertFalse(is_email_enabled("submission_reminder"))

    def test_locked_types_ignore_the_global_switch(self):
        disable_globally()
        for key in ("login_code", "password_reset", "password_changed"):
            with self.subTest(key=key):
                self.assertTrue(is_email_enabled(key))

    def test_locked_types_ignore_their_own_switch(self):
        for key in ("login_code", "password_reset", "password_changed"):
            SystemEmailTemplate.objects.create(key=key, is_enabled=False)
        for key in ("login_code", "password_reset", "password_changed"):
            with self.subTest(key=key):
                self.assertTrue(is_email_enabled(key))

    def test_database_error_fails_open(self):
        with mock.patch.object(SystemEmailTemplate.objects, "filter", side_effect=DatabaseError), \
                self.assertLogs("apps.services.system_email", level="ERROR") as logs:
            self.assertTrue(is_email_enabled("announcement"))
        self.assertIn("toggle_check_failed", logs.output[0])

    def test_unknown_type_raises(self):
        with self.assertRaises(KeyError):
            is_email_enabled("not_a_real_email")


class FillTagsTests(TestCase):
    def test_replaces_allowed_tags_from_their_context_keys(self):
        text = "Hi {{ first_name }}, link: {{reset_link}} ({{ expiry_minutes }} min)"
        self.assertEqual(
            fill_tags(text, "password_reset", RESET_CONTEXT),
            "Hi Alex, link: https://example.test/reset?token=abc (30 min)",
        )

    def test_escapes_values_in_html(self):
        context = {**RESET_CONTEXT, "First_Name": "<script>alert(1)</script>"}
        filled = fill_tags("Hi {{ first_name }}", "password_reset", context)
        self.assertEqual(filled, "Hi &lt;script&gt;alert(1)&lt;/script&gt;")

    def test_does_not_escape_when_asked_not_to(self):
        context = {**RESET_CONTEXT, "First_Name": "O'Brien & Co"}
        self.assertEqual(fill_tags("{{ first_name }}", "password_reset", context, escape=False), "O'Brien & Co")

    def test_html_snippet_tags_are_not_escaped(self):
        snippet = "<ul><li>CRISPR Research: 2</li></ul>"
        filled = fill_tags("{{ unread_group_list }}", "unread_messages", {"UNREAD_GROUP_LIST": snippet})
        self.assertEqual(filled, snippet)

    def test_leaves_tags_the_type_does_not_allow(self):
        self.assertEqual(
            fill_tags("Hi {{ group_name }}", "password_reset", RESET_CONTEXT),
            "Hi {{ group_name }}",
        )

    def test_template_syntax_is_never_executed(self):
        text = "{% include 'emails/base.html' %} {{ settings.SECRET_KEY }} {{ first_name|upper }}"
        self.assertEqual(fill_tags(text, "password_reset", RESET_CONTEXT), text)

    def test_missing_and_none_values_become_empty(self):
        self.assertEqual(fill_tags("[{{ first_name }}]", "password_reset", {}), "[]")
        self.assertEqual(fill_tags("[{{ first_name }}]", "password_reset", {"First_Name": None}), "[]")

    def test_formats_datetimes(self):
        changed = datetime(2026, 9, 18, 10, 30, tzinfo=dt_timezone.utc)
        filled = fill_tags("{{ changed_at }}", "password_changed", {"CHANGED_AT": changed})
        self.assertEqual(filled, "18 Sep 2026, 10:30")


class RenderDefaultTests(TestCase):
    def test_uses_default_subject_and_template_file(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT)
        self.assertEqual(rendered.subject, "BIOTech Futures: Update your password")
        self.assertIn("https://example.test/reset?token=abc", rendered.html)
        self.assertIn("Hi Alex,", rendered.html)

    def test_uses_the_senders_plain_text_when_given(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT, default_text="plain version")
        self.assertEqual(rendered.text, "plain version")

    def test_derives_plain_text_without_css(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT)
        self.assertIn("Hi Alex,", rendered.text)
        self.assertIn("Update password (https://example.test/reset?token=abc)", rendered.text)
        # No leftover CSS or markup (the footer's "Name <address>" is fine).
        for leftover in ("{", "mso-", "color:", "<p", "<table", "<a ", "</"):
            self.assertNotIn(leftover, rendered.text)

    def test_blank_saved_row_still_uses_defaults(self):
        SystemEmailTemplate.objects.create(key="password_reset", subject="  ", body_html="")
        rendered = render_system_email("password_reset", RESET_CONTEXT)
        self.assertEqual(rendered.subject, "BIOTech Futures: Update your password")
        self.assertIn("https://example.test/reset?token=abc", rendered.html)

    def test_database_error_falls_back_to_defaults(self):
        with mock.patch.object(SystemEmailTemplate.objects, "filter", side_effect=DatabaseError), \
                self.assertLogs("apps.services.system_email", level="ERROR"):
            rendered = render_system_email("login_code", {"OTP_CODE": "123456", "MAGIC_LINK": "#"})
        self.assertEqual(rendered.subject, "BIOTech Futures: Log in securely")
        self.assertIn("123456", rendered.html)


class RenderOverrideTests(TestCase):
    def setUp(self):
        SystemEmailTemplate.objects.create(
            key="password_reset",
            subject="Reset for {{ first_name }}",
            body_html="<p>Hello {{ first_name }}, use <a href=\"{{ reset_link }}\">this link</a>.</p>",
        )

    def test_uses_saved_subject_and_body_inside_the_brand_layout(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT)
        self.assertEqual(rendered.subject, "Reset for Alex")
        self.assertIn("<p>Hello Alex, use <a href=\"https://example.test/reset?token=abc\">this link</a>.</p>", rendered.html)
        self.assertIn("cid:btf-logo", rendered.html)
        self.assertIn("biotechfutures.org", rendered.html)

    def test_plain_text_comes_from_the_saved_body(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT, default_text="ignored")
        self.assertEqual(rendered.text, "Hello Alex, use this link (https://example.test/reset?token=abc).")

    def test_user_data_in_the_body_is_escaped(self):
        context = {**RESET_CONTEXT, "First_Name": "<img src=x onerror=alert(1)>"}
        rendered = render_system_email("password_reset", context)
        self.assertNotIn("<img src=x", rendered.html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", rendered.html)

    def test_subject_is_flattened_to_one_line(self):
        rendered = render_system_email("password_reset", RESET_CONTEXT, subject="Hi\r\nBcc: someone@example.test")
        self.assertEqual(rendered.subject, "Hi Bcc: someone@example.test")

    def test_passed_subject_and_body_override_the_saved_row(self):
        rendered = render_system_email(
            "password_reset", RESET_CONTEXT, subject="Preview {{ first_name }}", body="<p>Draft</p>",
        )
        self.assertEqual(rendered.subject, "Preview Alex")
        self.assertIn("<p>Draft</p>", rendered.html)
        self.assertNotIn("Hello Alex", rendered.html)

    def test_subject_only_override_keeps_the_default_body(self):
        SystemEmailTemplate.objects.filter(key="password_reset").update(body_html="")
        rendered = render_system_email("password_reset", RESET_CONTEXT)
        self.assertEqual(rendered.subject, "Reset for Alex")
        self.assertIn("Hi Alex,", rendered.html)


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class SendTests(TestCase):
    def test_sends_one_branded_email(self):
        result = send_system_email("password_reset", "alex@example.test", RESET_CONTEXT, default_text="plain")
        self.assertEqual(result, SENT)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["alex@example.test"])
        self.assertEqual(message.subject, "BIOTech Futures: Update your password")
        self.assertEqual(message.body, "plain")
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("https://example.test/reset?token=abc", html)
        self.assertEqual(message.mixed_subtype, "related")

    def test_skips_when_switched_off(self):
        SystemEmailTemplate.objects.create(key="announcement", is_enabled=False)
        with self.assertLogs("apps.services.system_email", level="INFO"):
            result = send_system_email("announcement", "alex@example.test", {})
        self.assertEqual(result, SKIPPED)
        self.assertEqual(mail.outbox, [])

    def test_login_code_still_sends_with_everything_switched_off(self):
        disable_globally()
        SystemEmailTemplate.objects.create(key="login_code", is_enabled=False)
        result = send_system_email("login_code", "alex@example.test", {"OTP_CODE": "123456", "MAGIC_LINK": "#"})
        self.assertEqual(result, SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_background_send_goes_through_the_mail_pool(self):
        with mock.patch("apps.services.system_email.send_async") as send_async:
            result = send_system_email("password_reset", "alex@example.test", RESET_CONTEXT, background=True)
        self.assertEqual(result, SENT)
        send_async.assert_called_once()
        self.assertEqual(send_async.call_args.kwargs["kind"], "password_reset")

    def test_send_failure_returns_failed_without_raising(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")), \
                self.assertLogs("apps.services.system_email", level="ERROR") as logs:
            result = send_system_email("password_reset", "alex@example.test", RESET_CONTEXT)
        self.assertEqual(result, FAILED)
        # The error type is logged, never the recipient's address.
        self.assertIn("error=OSError", logs.output[0])
        self.assertNotIn("alex@example.test", logs.output[0])

    def test_custom_from_address(self):
        send_system_email("password_reset", "alex@example.test", RESET_CONTEXT, from_email="Connect <connect@example.test>")
        self.assertEqual(mail.outbox[0].from_email, "Connect <connect@example.test>")


class HtmlToTextTests(TestCase):
    def test_drops_styles_comments_and_hidden_preheader(self):
        html = (
            "<html><head><style>p { color: red; }</style></head><body>"
            "<!-- note --><div style=\"display:none;\">preheader</div>"
            "<p>Hello</p></body></html>"
        )
        self.assertEqual(html_to_text(html), "Hello")

    def test_keeps_paragraph_breaks_list_items_and_link_targets(self):
        html = "<p>One</p><p>Two <a href=\"https://x.test\">site</a></p><ul><li>A</li><li>B</li></ul>"
        self.assertEqual(html_to_text(html), "One\nTwo site (https://x.test)\n- A\n- B")

    def test_unescapes_entities(self):
        self.assertEqual(html_to_text("<p>Tom &amp; Jerry &mdash; hi</p>"), "Tom & Jerry — hi")
