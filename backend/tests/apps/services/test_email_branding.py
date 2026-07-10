"""
Sender/footer branding for transactional emails.
Run with: python manage.py test tests.apps.services.test_email_branding
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.test import TestCase

from apps.services.email_branding import brand_context


class EmailSenderBrandingTests(TestCase):
    def test_from_address_is_pinned_and_on_brand(self):
        # Sender mailbox is pinned in settings (not env-driven), so a misconfigured
        # deploy can't ship an off-brand From name like "Biotech Futures".
        self.assertEqual(settings.EMAIL_FROM_ADDRESS, "info@biotechfutures.org")
        self.assertEqual(
            settings.DEFAULT_FROM_EMAIL,
            "BIOTech Futures <info@biotechfutures.org>",
        )

    def test_footer_shows_branded_name_and_email(self):
        html = render_to_string("emails/login.html", {
            **brand_context(),
            "MAGIC_LINK": "#",
            "OTP_CODE": "000000",
            "EXPIRY_MINUTES": 10,
            "First_Name": "William",
        })
        # "Add <name> <<email>> to your address book" — mailto stays on the bare mailbox.
        self.assertIn("BIOTech Futures &lt;info@biotechfutures.org&gt;", html)
        self.assertIn('href="mailto:info@biotechfutures.org"', html)
