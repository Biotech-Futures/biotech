"""Tests for the admin system-email API and its service layer.

Covers what administrators can do to a system email and, just as importantly,
what they cannot: switch off the login email, save a merge tag the email type
does not support, or smuggle markup past the sanitiser. Also pins the
fallback contract — an email with no saved wording still renders its template
file, so nothing changes for recipients until an admin edits something.
"""

from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.system_email import (
    get_email_settings,
    get_email_template,
    list_email_templates,
    preview_email_template,
    restore_email_template,
    send_test_email,
    update_email_settings,
    update_email_template,
)
from apps.services.email_registry import EMAIL_REGISTRY
from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
class SystemEmailAdminServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            first_name="Ada",
            last_name="Admin",
        )

    # -- listing -----------------------------------------------------------

    def test_list_includes_every_registry_type_with_defaults(self):
        result = list_email_templates()
        items = result["data"]["items"]
        self.assertEqual(len(items), len(EMAIL_REGISTRY))
        by_key = {item["key"]: item for item in items}
        self.assertEqual(set(by_key), set(EMAIL_REGISTRY))

        login = by_key["login_code"]
        self.assertTrue(login["locked"])
        self.assertTrue(login["enabled"])
        self.assertFalse(login["usingSavedContent"])
        self.assertEqual(login["subject"], "")
        self.assertEqual(login["body"], "")
        self.assertEqual(login["defaultSubject"], EMAIL_REGISTRY["login_code"].default_subject)
        self.assertIn("magic_link", {tag["name"] for tag in login["mergeTags"]})

    # -- detail ------------------------------------------------------------

    def test_get_unknown_type_returns_no_data(self):
        result = get_email_template("nope")
        self.assertIsNone(result["data"])

    def test_get_reflects_saved_state(self):
        SystemEmailTemplate.objects.create(
            key="password_reset",
            subject="Reset now",
            body_html="<p>Hi</p>",
            is_enabled=False,
        )
        result = get_email_template("password_reset")
        self.assertEqual(result["data"]["subject"], "Reset now")
        self.assertEqual(result["data"]["body"], "<p>Hi</p>")
        self.assertFalse(result["data"]["enabled"])
        self.assertTrue(result["data"]["usingSavedContent"])

    # -- update ------------------------------------------------------------

    def test_list_exposes_default_subject_and_default_body_for_prefill(self):
        result = list_email_templates()
        by_key = {item["key"]: item for item in result["data"]["items"]}

        reset = by_key["password_reset"]
        self.assertEqual(reset["defaultSubject"], "{{ brand_name }}: Update your password")
        # The built-in body is rendered with sample values so the editor can
        # pre-fill with the content recipients would actually see.
        self.assertIn("Update your password", reset["defaultBody"])
        self.assertIn("Alex", reset["defaultBody"])

        login = by_key["login_code"]
        self.assertIn("Log in to", login["defaultBody"])

    def test_default_body_is_rendered_from_any_app_template_when_not_customised(self):
        # Template files live in each app's own templates directory (APP_DIRS);
        # the chat digest one should resolve just like the services one.
        result = preview_email_template("unread_messages")
        self.assertIsNotNone(result["data"])
        self.assertEqual(
            result["data"]["subject"], "You have 3 unread messages on BIOTech Connect"
        )
        self.assertIn("<!doctype html>", result["data"]["html"])

    def test_preview_still_accepts_unsaved_edits_for_app_templates(self):
        result = preview_email_template(
            "unread_messages", body="<p>You have {{ total_unread }} new messages.</p>"
        )
        self.assertIsNotNone(result["data"])
        self.assertIn("<p>You have 3 new messages.</p>", result["data"]["html"])

    def test_update_creates_row_and_saves_wording(self):
        result = update_email_template(
            "password_reset",
            {"subject": "Hello {{ first_name }}", "body": "<p>Reset here</p>"},
            requested_by=self.admin,
        )
        self.assertIsNotNone(result["data"])
        row = SystemEmailTemplate.objects.get(key="password_reset")
        self.assertEqual(row.subject, "Hello {{ first_name }}")
        self.assertEqual(row.body_html, "<p>Reset here</p>")
        self.assertEqual(row.updated_by, self.admin)
        self.assertTrue(row.is_enabled)

    def test_update_sanitises_script_out_of_body(self):
        dirty = '<p>Hi</p><script>alert("x")</script><iframe src="http://x"></iframe>'
        update_email_template(
            "password_reset", {"body": dirty}, requested_by=self.admin
        )
        row = SystemEmailTemplate.objects.get(key="password_reset")
        self.assertNotIn("<script", row.body_html)
        self.assertNotIn("<iframe", row.body_html)
        self.assertIn("<p>Hi</p>", row.body_html)

    def test_update_rejects_unknown_merge_tag(self):
        result = update_email_template(
            "password_reset",
            {"subject": "Hi {{ secret_sauce }}"},
            requested_by=self.admin,
        )
        self.assertIsNone(result["data"])
        self.assertIn("secret_sauce", result["msg"])
        self.assertFalse(
            SystemEmailTemplate.objects.filter(key="password_reset").exists()
        )

    def test_update_rejects_unknown_merge_tag_in_body(self):
        result = update_email_template(
            "password_reset",
            {"body": "<p>{{ brand_name }}{{ nope }}</p>"},
            requested_by=self.admin,
        )
        self.assertIsNone(result["data"])
        self.assertIn("nope", result["msg"])

    def test_update_refuses_to_switch_off_locked_type(self):
        result = update_email_template(
            "login_code", {"enabled": False}, requested_by=self.admin
        )
        self.assertIsNone(result["data"])
        self.assertIn("cannot be switched off", result["msg"])
        self.assertFalse(SystemEmailTemplate.objects.filter(key="login_code").exists())

    def test_locked_type_can_still_be_edited(self):
        result = update_email_template(
            "login_code",
            {"subject": "Sign in to {{ brand_name }}", "body": "<p>Code {{ otp_code }}</p>"},
            requested_by=self.admin,
        )
        self.assertIsNotNone(result["data"])
        self.assertTrue(result["data"]["enabled"])

    def test_toggle_does_not_disturb_wording(self):
        update_email_template(
            "password_reset",
            {"subject": "Keep me", "body": "<p>Keep</p>"},
            requested_by=self.admin,
        )
        update_email_template(
            "password_reset", {"enabled": False}, requested_by=self.admin
        )
        row = SystemEmailTemplate.objects.get(key="password_reset")
        self.assertEqual(row.subject, "Keep me")
        self.assertEqual(row.body_html, "<p>Keep</p>")
        self.assertFalse(row.is_enabled)

    def test_blank_body_means_use_template_file_again(self):
        update_email_template(
            "password_reset",
            {"subject": "Something", "body": "<p>Something</p>"},
            requested_by=self.admin,
        )
        result = update_email_template(
            "password_reset", {"subject": "", "body": ""}, requested_by=self.admin
        )
        self.assertFalse(result["data"]["usingSavedContent"])
        # Row still exists so the enabled state survives.
        row = SystemEmailTemplate.objects.get(key="password_reset")
        self.assertTrue(row.is_enabled)

    # -- restore -----------------------------------------------------------

    def test_restore_clears_wording_but_keeps_disabled_state(self):
        update_email_template(
            "password_reset",
            {"subject": "Old", "body": "<p>Old</p>", "enabled": False},
            requested_by=self.admin,
        )
        result = restore_email_template("password_reset", requested_by=self.admin)
        self.assertFalse(result["data"]["usingSavedContent"])
        self.assertFalse(result["data"]["enabled"])
        row = SystemEmailTemplate.objects.get(key="password_reset")
        self.assertEqual(row.subject, "")
        self.assertEqual(row.body_html, "")

    def test_restore_with_nothing_saved_is_a_noop(self):
        result = restore_email_template("password_reset", requested_by=self.admin)
        self.assertIsNotNone(result["data"])
        self.assertFalse(result["data"]["usingSavedContent"])

    # -- preview -----------------------------------------------------------

    def test_preview_uses_template_file_when_nothing_saved(self):
        result = preview_email_template("login_code")
        # The login template's branded shell makes it into the preview.
        self.assertIn("<!doctype html>", result["data"]["html"])
        self.assertIn("Log in securely", result["data"]["subject"])

    def test_preview_fills_sample_tags_from_unsaved_edits(self):
        result = preview_email_template(
            "password_reset",
            subject="Hi {{ first_name }}",
            body="<p>Go to {{ reset_link }}</p>",
        )
        self.assertEqual(result["data"]["subject"], "Hi Alex")
        self.assertIn("https://biotechfutures.org/#/auth/reset-password", result["data"]["html"])

    def test_preview_sanitises_unsaved_body(self):
        result = preview_email_template(
            "password_reset", body='<p>ok</p><script>alert("x")</script>'
        )
        self.assertIn("<p>ok</p>", result["data"]["html"])
        self.assertNotIn("<script", result["data"]["html"])

    def test_preview_rejects_unknown_tag(self):
        result = preview_email_template("password_reset", subject="{{ not_a_tag }}")
        self.assertIsNone(result["data"])
        self.assertIn("not_a_tag", result["msg"])

    # -- test send ---------------------------------------------------------

    def test_test_send_goes_only_to_the_admin(self):
        mail.outbox = []
        result = send_test_email("password_reset", requested_by=self.admin)
        self.assertEqual(result["data"]["sentTo"], "admin@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])

    def test_test_send_works_even_when_type_is_disabled(self):
        SystemEmailTemplate.objects.create(key="password_reset", is_enabled=False)
        mail.outbox = []
        result = send_test_email("password_reset", requested_by=self.admin)
        self.assertIsNotNone(result["data"])
        self.assertEqual(len(mail.outbox), 1)

    def test_test_send_failure_returns_no_data(self):
        with patch(
            "apps.admin.services.system_email.build_message",
        ) as build:
            build.return_value.send.side_effect = Exception("smtp down")
            result = send_test_email("password_reset", requested_by=self.admin)
        self.assertIsNone(result["data"])

    # -- settings ----------------------------------------------------------

    def test_settings_default_to_enabled(self):
        result = get_email_settings()
        self.assertTrue(result["data"]["emailsEnabled"])

    def test_settings_can_be_disabled(self):
        result = update_email_settings(False, requested_by=self.admin)
        self.assertFalse(result["data"]["emailsEnabled"])
        self.assertFalse(SystemEmailSettings.get().emails_enabled)

    def test_unknown_type_update_and_restore_return_no_data(self):
        self.assertIsNone(
            update_email_template("nope", {"enabled": True}, requested_by=self.admin)["data"]
        )
        self.assertIsNone(restore_email_template("nope", requested_by=self.admin)["data"])
        self.assertIsNone(
            send_test_email("nope", requested_by=self.admin)["data"]
        )


@override_settings(EMAIL_BACKEND=LOCMEM)
class SystemEmailAdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            first_name="Ada",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_list_requires_admin(self):
        outsider = User.objects.create_user(email="user@example.com", password="pw")
        client = APIClient()
        client.force_authenticate(outsider)
        response = client.get("/api/v1/admin/email-template/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_types(self):
        response = self.client.get("/api/v1/admin/email-template/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("login_code", {item["key"] for item in body["data"]["items"]})

    def test_detail_unknown_returns_404(self):
        response = self.client.get("/api/v1/admin/email-template/nope/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_saves_and_returns_sanitised_body(self):
        response = self.client.patch(
            "/api/v1/admin/email-template/password_reset/",
            {"subject": "Hi {{ first_name }}", "body": "<p>ok</p><script>x</script>"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()["data"]
        self.assertEqual(body["subject"], "Hi {{ first_name }}")
        self.assertIn("<p>ok</p>", body["body"])
        self.assertNotIn("<script", body["body"])
        self.assertTrue(body["usingSavedContent"])

    def test_patch_unknown_tag_returns_400(self):
        response = self.client.patch(
            "/api/v1/admin/email-template/password_reset/",
            {"subject": "{{ nope }}"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nope", response.json()["msg"])

    def test_patch_locked_disable_returns_400(self):
        response = self.client.patch(
            "/api/v1/admin/email-template/login_code/",
            {"enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be switched off", response.json()["msg"])

    def test_patch_unknown_type_returns_404(self):
        response = self.client.patch(
            "/api/v1/admin/email-template/nope/", {"enabled": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_returns_rendered_html(self):
        response = self.client.post(
            "/api/v1/admin/email-template/password_reset/preview/",
            {"subject": "Hi {{ first_name }}", "body": "<p>{{ reset_link }}</p>"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["subject"], "Hi Alex")
        self.assertIn("<!doctype html>", data["html"])
        self.assertIn("reset-password", data["html"])

    def test_preview_renders_an_app_template_with_sample_values(self):
        response = self.client.post(
            "/api/v1/admin/email-template/unread_messages/preview/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["subject"], "You have 3 unread messages on BIOTech Connect")

    def test_test_send_sends_to_requesting_admin(self):
        mail.outbox = []
        response = self.client.post(
            "/api/v1/admin/email-template/password_reset/test-send/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["sentTo"], "admin@example.com")
        self.assertEqual(len(mail.outbox), 1)

    def test_restore_clears_saved_wording(self):
        self.client.patch(
            "/api/v1/admin/email-template/password_reset/",
            {"subject": "Temp", "body": "<p>Temp</p>"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/admin/email-template/password_reset/restore-default/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertFalse(data["usingSavedContent"])
        self.assertEqual(data["subject"], "")

    def test_settings_get_and_patch(self):
        response = self.client.get("/api/v1/admin/email-settings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"]["emailsEnabled"])

        response = self.client.patch(
            "/api/v1/admin/email-settings/", {"enabled": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["data"]["emailsEnabled"])

    def test_settings_patch_requires_boolean(self):
        response = self.client.patch(
            "/api/v1/admin/email-settings/", {"enabled": "not-a-bool"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)