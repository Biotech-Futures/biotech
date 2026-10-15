"""The stored QuickEmailVerification answers and the credit balance
(apps.users.models.email_verification), and their read-only admin pages."""
from datetime import timedelta

from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.users.models import EmailVerification, EmailVerificationCredits, User

Status = EmailVerification.Status


def _stored(email, status=Status.VALID, days_old=0, **fields):
    return EmailVerification.objects.create(
        email=email, status=status, checked_at=timezone.now() - timedelta(days=days_old), **fields,
    )


class EmailVerificationTests(TestCase):
    def test_addresses_are_stored_stripped_and_lower_case(self):
        row = _stored("  Kid@Example.COM ")

        self.assertEqual(row.email, "kid@example.com")
        self.assertEqual(EmailVerification.objects.get().email, "kid@example.com")

    def test_one_address_is_one_row_whatever_its_casing(self):
        _stored("kid@example.com")

        with self.assertRaises(IntegrityError), transaction.atomic():
            _stored("KID@example.com")

    def test_flags_default_to_off_and_safe_to_send_to_not_said(self):
        row = _stored("kid@example.com")

        self.assertEqual((row.accept_all, row.disposable, row.role, row.free), (False,) * 4)
        self.assertIsNone(row.safe_to_send)
        self.assertEqual((row.reason, row.did_you_mean), ("", ""))

    def test_only_valid_invalid_and_unknown_can_be_stored(self):
        self.assertEqual(set(Status.values), {"valid", "invalid", "unknown"})


class ReusableAnswerTests(TestCase):
    def test_recent_valid_and_invalid_answers_are_reused(self):
        _stored("good@example.com", Status.VALID, days_old=10)
        _stored("bad@example.com", Status.INVALID, days_old=10)

        found = EmailVerification.reusable(["good@example.com", "bad@example.com"], max_age_days=180)

        self.assertEqual({email: row.status for email, row in found.items()},
                         {"good@example.com": "valid", "bad@example.com": "invalid"})

    def test_unknown_answers_are_never_reused(self):
        _stored("maybe@example.com", Status.UNKNOWN)

        self.assertEqual(EmailVerification.reusable(["maybe@example.com"], max_age_days=180), {})

    def test_answers_older_than_the_maximum_age_are_not_reused(self):
        _stored("old@example.com", days_old=181)
        _stored("recent@example.com", days_old=179)

        found = EmailVerification.reusable(["old@example.com", "recent@example.com"], max_age_days=180)

        self.assertEqual(list(found), ["recent@example.com"])

    def test_the_maximum_age_is_whatever_the_caller_passes(self):
        _stored("kid@example.com", days_old=40)

        self.assertEqual(EmailVerification.reusable(["kid@example.com"], max_age_days=30), {})
        self.assertIn("kid@example.com", EmailVerification.reusable(["kid@example.com"], max_age_days=60))

    def test_addresses_are_looked_up_whatever_their_casing_and_spacing(self):
        _stored("kid@example.com")

        found = EmailVerification.reusable([" KID@Example.com "], max_age_days=180)

        self.assertEqual(list(found), ["kid@example.com"])

    def test_addresses_never_checked_and_blanks_are_left_out(self):
        _stored("kid@example.com")

        found = EmailVerification.reusable(["kid@example.com", "new@example.com", "", "  ", None],
                                           max_age_days=180)

        self.assertEqual(list(found), ["kid@example.com"])

    def test_nothing_to_look_up_finds_nothing(self):
        with self.assertNumQueries(0):
            self.assertEqual(EmailVerification.reusable([], max_age_days=180), {})
            self.assertEqual(EmailVerification.reusable(["", None], max_age_days=180), {})


class CreditsTests(TestCase):
    def test_the_balance_is_unknown_until_the_service_reports_it(self):
        credits = EmailVerificationCredits.get()

        self.assertIsNone(credits.remaining)
        self.assertIsNone(credits.updated_at)
        self.assertEqual(credits.alerted_thresholds, [])
        self.assertIsNone(credits.lookups_on)
        self.assertEqual(credits.lookups_today, 0)
        self.assertEqual(str(credits), "Unknown")

    def test_there_is_only_ever_one_row(self):
        EmailVerificationCredits.get()
        EmailVerificationCredits(remaining=2500).save()
        EmailVerificationCredits.get()

        self.assertEqual(EmailVerificationCredits.objects.count(), 1)
        credits = EmailVerificationCredits.objects.get()
        self.assertEqual(credits.pk, EmailVerificationCredits.SINGLETON_PK)
        self.assertEqual(credits.remaining, 2500)
        self.assertEqual(str(credits), "2500 credits remaining")

    def test_sent_alerts_are_kept(self):
        credits = EmailVerificationCredits.get()
        credits.remaining, credits.alerted_thresholds = 450, [500]
        credits.save()

        self.assertEqual(EmailVerificationCredits.get().alerted_thresholds, [500])


class ReadOnlyAdminTests(TestCase):
    def setUp(self):
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(email="admin@example.com", password="pw-for-tests-only")
        self.request = request

    def test_both_are_shown_in_django_admin_but_cannot_be_added_or_changed(self):
        for model in (EmailVerification, EmailVerificationCredits):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]

                self.assertTrue(model_admin.has_view_permission(self.request))
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request))

    def test_a_stored_answer_can_be_deleted_so_the_address_is_checked_again(self):
        row = _stored("kid@example.com", Status.INVALID)
        model_admin = admin.site._registry[EmailVerification]

        self.assertTrue(model_admin.has_delete_permission(self.request))
        self.assertTrue(model_admin.has_delete_permission(self.request, row))

    def test_the_credit_balance_cannot_be_deleted(self):
        credits = EmailVerificationCredits.get()
        model_admin = admin.site._registry[EmailVerificationCredits]

        self.assertFalse(model_admin.has_delete_permission(self.request))
        self.assertFalse(model_admin.has_delete_permission(self.request, credits))

    def test_admins_without_the_permission_still_cannot_delete_answers(self):
        self.request.user = User.objects.create_user(email="staff@example.com", is_staff=True)

        self.assertFalse(admin.site._registry[EmailVerification].has_delete_permission(self.request))
