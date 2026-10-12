"""
Storage for admin-edited system emails and the global email switch.
Run with: python manage.py test tests.apps.services.test_system_email_models
"""

from django.db import IntegrityError
from django.test import TestCase

from apps.services.models import SystemEmailSettings, SystemEmailTemplate


class SystemEmailTemplateTests(TestCase):
    def test_new_row_defaults_to_enabled_with_no_custom_content(self):
        row = SystemEmailTemplate.objects.create(key="password_reset")
        self.assertTrue(row.is_enabled)
        self.assertEqual(row.subject, "")
        self.assertEqual(row.body_html, "")
        self.assertFalse(row.has_custom_content)

    def test_custom_content_needs_both_subject_and_body(self):
        subject_only = SystemEmailTemplate(key="a", subject="Hi", body_html="   ")
        body_only = SystemEmailTemplate(key="b", subject="", body_html="<p>Hi</p>")
        both = SystemEmailTemplate(key="c", subject="Hi", body_html="<p>Hi</p>")
        self.assertFalse(subject_only.has_custom_content)
        self.assertFalse(body_only.has_custom_content)
        self.assertTrue(both.has_custom_content)

    def test_key_is_unique(self):
        SystemEmailTemplate.objects.create(key="login_code")
        with self.assertRaises(IntegrityError):
            SystemEmailTemplate.objects.create(key="login_code")


class SystemEmailSettingsTests(TestCase):
    def test_get_creates_enabled_row_when_missing(self):
        self.assertFalse(SystemEmailSettings.objects.exists())
        settings_row = SystemEmailSettings.get()
        self.assertTrue(settings_row.emails_enabled)
        self.assertEqual(SystemEmailSettings.objects.count(), 1)

    def test_get_returns_the_same_row(self):
        first = SystemEmailSettings.get()
        first.emails_enabled = False
        first.save()
        self.assertFalse(SystemEmailSettings.get().emails_enabled)
        self.assertEqual(SystemEmailSettings.objects.count(), 1)

    def test_saving_a_new_instance_never_creates_a_second_row(self):
        SystemEmailSettings.get()
        SystemEmailSettings(emails_enabled=False).save()
        self.assertEqual(SystemEmailSettings.objects.count(), 1)
        self.assertFalse(SystemEmailSettings.get().emails_enabled)
