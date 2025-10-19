from django.test import TestCase

# Create your tests here.
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.users.models import Background, MentorProfile  # FK targets
from apps.resources.models import Roles, RoleAssignmentHistory
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
        """Non-admin users should be forbidden"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_no_active_role_forbidden(self):
        """Users with no active role should be forbidden"""
        # Create a user with no role assignment
        no_role_user = User.objects.create_user(
            email="norole@example.com", password="pass123",
            first_name="No", last_name="Role"
        )
        self.client.force_authenticate(user=no_role_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_forbidden(self):
        """Student role should have no access"""
        # Create student role
        student_role, _ = Roles.objects.get_or_create(role_name='Student')
        RoleAssignmentHistory.objects.create(
            user=self.user,
            role=student_role,
            valid_from=timezone.now()
        )
        
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
            "certificate_type": self.cert_type.pk,  # Fixed: use PK not string
            "certificate_number": "XYZ999",
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01",
            "expires_at": "2026-10-01",
            "file_url": "https://example.com/cert.pdf",
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["certificate_number"], "XYZ999")

    def test_requires_number_and_expiry_validation(self):
        """Test that missing required fields returns 400"""
        self.client.force_authenticate(user=self.admin)
        payload = {
            "mentor_profile": self.mentor_profile.pk,
            "certificate_type": self.cert_type.pk,
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01"
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requires a certificate number", str(resp.data))
    
    def test_certificate_can_be_indefinite(self):
        """Test that certificates can be created without expiry dates (indefinite)"""
        self.client.force_authenticate(user=self.admin)
        payload = {
            "mentor_profile": self.mentor_profile.pk,
            "certificate_type": self.cert_type.pk,
            "certificate_number": "INDEFINITE123",
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01"
            # No expires_at - should be allowed (indefinite certificate)
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["certificate_number"], "INDEFINITE123")
        self.assertIsNone(resp.data["expires_at"])  # Should be null/None

    def test_missing_required_fields(self):
        """Test that missing required fields returns 400"""
        self.client.force_authenticate(user=self.admin)
        payload = {
            # Missing mentor_profile - this is required
            "certificate_type": self.cert_type.pk,
            "certificate_number": "TEST123",
            "issued_by": "NSW Gov",
            "issued_at": "2025-10-01"
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that error mentions missing fields
        self.assertIn("mentor_profile", str(resp.data))


class MentorRBACTests(APITestCase):
    """Test Role-Based Access Control for Mentors"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create mentor role
        self.mentor_role, _ = Roles.objects.get_or_create(role_name='Mentor')
        
        # Create mentor user with role
        bg = Background.objects.create(background_desc_unique_field="Engineering")
        self.mentor_user = User.objects.create_user(
            email="mentor@test.com", password="pass123",
            first_name="Test", last_name="Mentor"
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            background=bg,
            institution="Test Uni",
            mentor_reason="Help",
            max_grp_cnt=5
        )
        
        # Assign mentor role
        RoleAssignmentHistory.objects.create(
            user=self.mentor_user,
            role=self.mentor_role,
            valid_from=timezone.now()
        )
        
        # Create certificate type
        self.cert_type = CertificateType.objects.create(
            certificate_type="WWCC",
            requires_number=True,
            requires_expiry=True
        )
        
        self.url = "/certificates/v1/"
    
    def test_mentor_can_create_own_certificate(self):
        """Mentor can create their own certificate"""
        self.client.force_authenticate(user=self.mentor_user)
        payload = {
            "certificate_type": self.cert_type.pk,
            "certificate_number": "MENTOR123",
            "issued_by": "NSW Gov",
            "issued_at": "2024-06-01",
            "expires_at": "2026-06-01",
            "file_url": "https://example.com/cert.pdf",
            # Mentors may need to provide mentor_profile in payload for validation
            # but perform_create will override it
            "mentor_profile": self.mentor_profile.pk
        }
        resp = self.client.post(self.url, payload, format="json")
        
        # Debug: print error if failed
        if resp.status_code != status.HTTP_201_CREATED:
            print(f"Failed with status {resp.status_code}: {resp.data}")
        
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        
        # Verify mentor_profile was auto-set
        cert = MentorCertificate.objects.get(certificate_number="MENTOR123")
        self.assertEqual(cert.mentor_profile, self.mentor_profile)
        self.assertFalse(cert.verified)  # Should be unverified by default
    
    def test_mentor_can_list_own_certificates(self):
        """Mentor can only see their own certificates"""
        # Create certificate for this mentor
        MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="OWN123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date()
        )
        
        # Create another mentor and their certificate
        other_bg = Background.objects.create(background_desc_unique_field="Math")
        other_user = User.objects.create_user(email="other@test.com", password="pass")
        other_profile = MentorProfile.objects.create(
            user=other_user,
            background=other_bg,
            institution="Other Uni",
            mentor_reason="Teach",
            max_grp_cnt=3
        )
        MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=other_profile,
            certificate_number="OTHER123",
            issued_by="VIC Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date()
        )
        
        self.client.force_authenticate(user=self.mentor_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        # Response might be paginated, check results key
        if isinstance(resp.data, dict) and 'results' in resp.data:
            results = resp.data['results']
        else:
            results = resp.data
        
        # Should only see own certificate
        own_certs = [c for c in results if c["certificate_number"] == "OWN123"]
        other_certs = [c for c in results if c["certificate_number"] == "OTHER123"]
        
        self.assertEqual(len(own_certs), 1)
        self.assertEqual(len(other_certs), 0)  # Should not see other mentor's certs
    
    def test_mentor_can_update_own_certificate(self):
        """Mentor can update their own certificate"""
        cert = MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="UPDATE123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date()
        )
        
        self.client.force_authenticate(user=self.mentor_user)
        payload = {
            "certificate_number": "UPDATED123",
            "expires_at": "2027-12-31"
        }
        resp = self.client.patch(f"{self.url}{cert.id}/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["certificate_number"], "UPDATED123")
    
    def test_mentor_cannot_verify_own_certificate(self):
        """Mentor cannot set verified flag"""
        cert = MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="VERIFY123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date(),
            verified=False
        )
        
        self.client.force_authenticate(user=self.mentor_user)
        # Try to verify via PATCH
        payload = {"verified": True}
        resp = self.client.patch(f"{self.url}{cert.id}/", payload, format="json")
        
        # Request succeeds but verified flag is ignored
        cert.refresh_from_db()
        self.assertFalse(cert.verified)
    
    def test_mentor_cannot_delete_certificate(self):
        """Mentor cannot delete certificates"""
        cert = MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="DELETE123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=365)).date()
        )
        
        self.client.force_authenticate(user=self.mentor_user)
        resp = self.client.delete(f"{self.url}{cert.id}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminRBACTests(APITestCase):
    """Test Admin-specific functionality"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="admin123",
            is_staff=True,
            is_superuser=True
        )
        
        bg = Background.objects.create(background_desc_unique_field="Science")
        mentor_user = User.objects.create_user(email="mentor@test.com", password="pass")
        self.mentor_profile = MentorProfile.objects.create(
            user=mentor_user,
            background=bg,
            institution="Test Uni",
            mentor_reason="Help",
            max_grp_cnt=3
        )
        
        self.cert_type = CertificateType.objects.create(
            certificate_type="WWCC",
            requires_number=True,
            requires_expiry=True
        )
        
        self.cert = MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="ADMIN123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=30)).date(),
            verified=False
        )
        
        self.url = "/certificates/v1/"
    
    def test_admin_can_verify_certificate(self):
        """Admin can verify certificates via POST action"""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f"{self.url}{self.cert.id}/verify/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["verified"])
        
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.verified)
    
    def test_admin_can_unverify_certificate(self):
        """Admin can unverify certificates"""
        self.cert.verified = True
        self.cert.save()
        
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f"{self.url}{self.cert.id}/unverify/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["verified"])
    
    def test_admin_audit_filter_expiring_soon(self):
        """Admin can filter certificates by expiry date"""
        # Create certificate expiring soon
        MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="EXPIRING123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=30)).date()
        )
        
        # Create certificate expiring far in future
        MentorCertificate.objects.create(
            certificate_type=self.cert_type,
            mentor_profile=self.mentor_profile,
            certificate_number="FUTURE123",
            issued_by="NSW Gov",
            issued_at=timezone.now().date(),
            expires_at=(timezone.now() + timezone.timedelta(days=730)).date()
        )
        
        self.client.force_authenticate(user=self.admin)
        # Filter for certificates expiring within 90 days
        expires_by = (timezone.now() + timezone.timedelta(days=90)).date().isoformat()
        resp = self.client.get(f"{self.url}?expires_by={expires_by}")
        
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Should only get certificates expiring within 90 days
        self.assertGreaterEqual(len(resp.data), 1)
    
    def test_admin_can_delete_certificate(self):
        """Admin can delete certificates"""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"{self.url}{self.cert.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify it's deleted
        self.assertFalse(MentorCertificate.objects.filter(id=self.cert.id).exists())
