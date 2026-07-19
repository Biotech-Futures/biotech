from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tasks.models import Task
from apps.users.models import AdminScope


User = get_user_model()


class AdminTaskRoleFanoutApiTests(APITestCase):
    """View-layer coverage: proves `assigned_role` survives the untyped
    `request.data` hand-off and that the literal role-recipients route is not
    swallowed by the `<int:task_id>` route next to it."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="task.admin@example.com", password="pass123",
            first_name="Task", last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.url = "/api/v1/admin/task/"
        self.recipients_url = "/api/v1/admin/task/role-recipients/"

        self.mentor_role = Roles.objects.create(role_name="mentor")
        self.mentors = []
        for i in range(3):
            user = User.objects.create_user(
                email=f"mentor{i}@example.com", password="pass123",
                first_name="Men", last_name=f"Tor{i}",
            )
            RoleAssignmentHistory.objects.create(
                user=user, role=self.mentor_role,
                valid_from=timezone.now() - timedelta(days=1),
            )
            self.mentors.append(user)

    def test_post_with_assigned_role_fans_out(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            {
                "name": "Mentor Training",
                "task_type": "individual",
                "assigned_role": "mentor",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["created_count"], 3)
        self.assertCountEqual(
            Task.objects.filter(name="Mentor Training").values_list(
                "assigned_user_id", flat=True
            ),
            [m.id for m in self.mentors],
        )

    def test_role_recipients_route_resolves_and_matches_fanout(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.recipients_url, {"role": "mentor"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 3)

    def test_role_recipients_rejects_unknown_role(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.recipients_url, {"role": "wizard"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_fan_out_or_preview(self):
        self.client.force_authenticate(user=self.mentors[0])

        created = self.client.post(
            self.url,
            {"name": "Nope", "task_type": "individual", "assigned_role": "mentor"},
            format="json",
        )
        previewed = self.client.get(self.recipients_url, {"role": "mentor"})

        self.assertIn(
            created.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            previewed.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertFalse(Task.objects.filter(name="Nope").exists())
