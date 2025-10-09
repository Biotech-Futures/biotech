from django.test import TestCase

# Create your tests here.
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.users.models import Background, MentorProfile  # FK targets
from .models import CertificateType, MentorCertificate

User = get_user_model()

class CertificateDetailTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.admin = User.objects.create_user(
            email="admin@example.com", password="admin123",
            first_name="A", last_name="D", is_staff=True
        )
        self.user = User.objects.create_user(
            email="user@example.com", password="pass123",
            first_name="U", last_name="S"
        )

        # Minimal mentor profile prerequisite
        bg = Background.objects.create(background_desc_unique_field="STEM")
        mentor_user = User.objects.create_user(
            email="mentor@example.com", password="m12345",
            first_name="M", last_name="E"
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=mentor_user, background=bg, institution="School", mentor_reason="Help", max_grp_cnt=3
        )

        # Cert type & certificate
        self.cert_type = CertificateType.objects.create(
            certificate_type="WWCC", requires_number=True, requires_expiry=True
        )
        self.cert = MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="ABC123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date(),
            file_url="https://example.com/cert.pdf",
            verified=False,
        )

        self.url = f"/certificates/v1/{self.cert.id}/"

    def test_admin_can_get_certificate_by_id(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["certificate_type"], "WWCC")
        self.assertEqual(resp.data["certificate_number"], "ABC123")
        self.assertIn("verified", resp.data)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_not_found_for_missing_id(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/certificates/v1/999999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

class CertificateCreateTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@example.com", password="admin123", is_staff=True
        )

        bg = Background.objects.create(background_desc_unique_field="Science")
        mentor_user = User.objects.create_user(
            email="mentor@example.com", password="m12345"
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=mentor_user, background=bg, institution="Uni", mentor_reason="Teach", max_grp_cnt=3
        )
        self.cert_type = CertificateType.objects.create(
            certificate_type="WWCC", requires_number=True, requires_expiry=True
        )
        self.url = "/certificates/v1/"

    def test_admin_can_create_certificate(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "mentor_profile": self.mentor_profile.pk,
            "certificate_type": "WWCC",
            "certificate_number": "XYZ999",
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01",
            "expires_at": "2026-10-01",
            "file_url": "https://example.com/cert.pdf",
            "verified": False
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["certificate_number"], "XYZ999")

    def test_requires_number_and_expiry_validation(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "mentor_profile": self.mentor_profile.pk,
            "certificate_type": "WWCC",
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01"
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requires a certificate number", str(resp.data))
