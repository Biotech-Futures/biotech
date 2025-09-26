from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()


class UserEmailFilterTestCase(TestCase):
    """Simple test for email filtering at /users/api/v1/users/?email="""

    def setUp(self):
        """Create test users"""
        self.client = Client()

        # Create admin user
        self.admin_user = User.objects.create_user(
            email="admin@admin.com",
            first_name="Admin",
            last_name="User",
            status=True
        )

        # Create another user
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            status=False
        )

    def test_email_filter_admin(self):
        """Test filtering for admin@admin.com"""
        response = self.client.get('/users/api/v1/users/?email=admin@admin.com')

        self.assertEqual(response.status_code, 200)
        # Should return HTML page with admin user
        self.assertContains(response, 'admin@admin.com')
        self.assertContains(response, 'Admin')

    def test_email_filter_regular_user(self):
        """Test filtering for user@example.com"""
        response = self.client.get('/users/api/v1/users/?email=user@example.com')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user@example.com')
        self.assertContains(response, 'Regular')

    def test_email_filter_nonexistent(self):
        """Test filtering for non-existent email"""
        response = self.client.get('/users/api/v1/users/?email=notfound@example.com')

        self.assertEqual(response.status_code, 200)
        # Should not contain any user emails
        self.assertNotContains(response, 'admin@admin.com')
        self.assertNotContains(response, 'user@example.com')

    def test_no_email_filter(self):
        """Test endpoint without email filter"""
        response = self.client.get('/users/api/v1/users/')

        self.assertEqual(response.status_code, 200)
        # Should contain both users
        self.assertContains(response, 'admin@admin.com')
        self.assertContains(response, 'user@example.com')
