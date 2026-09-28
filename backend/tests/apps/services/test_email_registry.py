"""
The registry of system email types and their merge tags.
Run with: python manage.py test tests.apps.services.test_email_registry
"""

from django.test import SimpleTestCase

from apps.services.email_registry import (
    EMAIL_REGISTRY,
    EMAIL_TYPES,
    MERGE_TAG_RE,
    extract_merge_tags,
    get_email_type,
    is_known_email_type,
    unknown_merge_tags,
)

EXPECTED_KEYS = {
    "login_code",
    "password_reset",
    "password_changed",
    "unread_messages",
    "rsvp_reminder",
    "event_promotion",
    "announcement",
    "submission_confirmation",
    "submission_reminder",
    "finalist_notification",
}


class RegistryShapeTests(SimpleTestCase):
    def test_contains_exactly_the_ten_email_types(self):
        self.assertEqual(set(EMAIL_REGISTRY), EXPECTED_KEYS)
        self.assertEqual(len(EMAIL_TYPES), len(EXPECTED_KEYS))

    def test_registry_keys_match_entries(self):
        for key, email_type in EMAIL_REGISTRY.items():
            self.assertEqual(email_type.key, key)

    def test_account_security_and_signin_emails_are_locked(self):
        locked = {t.key for t in EMAIL_TYPES if t.locked}
        self.assertEqual(locked, {"login_code", "password_reset", "password_changed"})

    def test_every_type_has_name_description_subject_and_template(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                self.assertTrue(email_type.name.strip())
                self.assertTrue(email_type.description.strip())
                self.assertTrue(email_type.default_subject.strip())
                self.assertTrue(email_type.default_template.startswith("emails/"))


class MergeTagTests(SimpleTestCase):
    def test_tag_names_are_snake_case_and_match_the_tag_syntax(self):
        for email_type in EMAIL_TYPES:
            for tag in email_type.merge_tags:
                with self.subTest(email_type=email_type.key, tag=tag.name):
                    self.assertRegex(tag.name, r"^[a-z][a-z0-9_]*$")
                    self.assertEqual(extract_merge_tags("{{ %s }}" % tag.name), {tag.name})

    def test_tags_are_unique_within_each_type(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                names = [tag.name for tag in email_type.merge_tags]
                self.assertEqual(len(names), len(set(names)))

    def test_every_tag_has_a_description_sample_and_context_key(self):
        for email_type in EMAIL_TYPES:
            for tag in email_type.merge_tags:
                with self.subTest(email_type=email_type.key, tag=tag.name):
                    self.assertTrue(tag.description.strip())
                    self.assertTrue(tag.sample.strip())
                    self.assertTrue(tag.context_key.strip())

    def test_every_type_offers_the_brand_tags(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                self.assertTrue({"brand_name", "brand_connect", "contact_email"} <= email_type.tag_names)

    def test_default_subjects_only_use_their_own_tags(self):
        for email_type in EMAIL_TYPES:
            with self.subTest(email_type=email_type.key):
                self.assertEqual(unknown_merge_tags(email_type.key, email_type.default_subject), set())

    def test_tag_lookup(self):
        login = get_email_type("login_code")
        self.assertEqual(login.tag("otp_code").context_key, "OTP_CODE")
        self.assertIsNone(login.tag("group_name"))


class HelperTests(SimpleTestCase):
    def test_extract_accepts_optional_spaces(self):
        self.assertEqual(extract_merge_tags("Hi {{first_name}} and {{  group_name  }}"), {"first_name", "group_name"})

    def test_django_style_expressions_are_not_tags(self):
        # Dotted lookups, capitals and filters must never be treated as tags,
        # so an admin can't reach settings or objects through the editor.
        for text in ("{{ settings.SECRET_KEY }}", "{{ User }}", "{{ first_name|upper }}", "{% include 'x' %}"):
            with self.subTest(text=text):
                self.assertEqual(extract_merge_tags(text), set())
                self.assertIsNone(MERGE_TAG_RE.search(text))

    def test_extract_handles_empty_input(self):
        self.assertEqual(extract_merge_tags(""), set())
        self.assertEqual(extract_merge_tags(None), set())

    def test_unknown_merge_tags(self):
        body = "Hi {{ first_name }}, your group {{ group_name }} code is {{ otp_code }}"
        self.assertEqual(unknown_merge_tags("login_code", body), {"group_name"})

    def test_unknown_email_type(self):
        self.assertFalse(is_known_email_type("not_a_real_email"))
        self.assertTrue(is_known_email_type("login_code"))
        with self.assertRaises(KeyError):
            get_email_type("not_a_real_email")
