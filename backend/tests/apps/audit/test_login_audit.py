from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.audit.models import AuditLog


User = get_user_model()


class LoginAuditTests(TestCase):
    def test_successful_password_login_creates_login_event(self):
        user = User.objects.create_user(
            email="login-audit@example.com",
            password="pass1234",
            first_name="Login",
            last_name="Audit",
        )

        response = self.client.post(
            reverse("password-login"),
            {"email": user.email, "password": "pass1234"},
        )

        self.assertEqual(response.status_code, 200)
        event = AuditLog.objects.get(action=AuditLog.ActionChoices.LOGIN)
        self.assertEqual(event.actor_user, user)
        self.assertEqual(event.entity_type, "user")
        self.assertEqual(event.entity_id, user.id)
        self.assertIsNone(event.before_state)
        self.assertIsNone(event.after_state)
