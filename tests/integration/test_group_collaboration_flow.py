from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.backend.base import AuthenticatedAPITestCase


class GroupCollaborationFlowTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_admin()
        self.mentor = self.create_user("integration.mentor@example.com", role="mentor", status="active")
        self.student = self.create_student("integration.student@example.com")

        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin.user)

        self.student_client = APIClient()
        self.student_client.force_authenticate(user=self.student.user)

    def test_group_task_lifecycle(self):
        # Admin creates group with student member
        create_group_url = reverse("groups:group-list")
        payload = {
            "groupId": "BTF200",
            "name": "Integration Builders",
            "track": "AUS-NSW",
            "status": "active",
            "mentorId": self.mentor.user.pk,
            "members": [{"userId": self.student.user.pk, "role": "student"}],
        }
        response = self.admin_client.post(create_group_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        group_id = response.json()["id"]

        # Student fetches detail
        detail_url = reverse("groups:group-detail", kwargs={"pk": group_id})
        response = self.student_client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Student creates milestone
        create_milestone_url = reverse("groups:group-create-milestone", kwargs={"pk": group_id})
        response = self.student_client.post(
            create_milestone_url,
            {"title": "Research Phase", "description": "Collect background data"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        milestone_id = response.json()["id"]

        # Student adds task
        add_task_url = reverse(
            "groups:group-add-task",
            kwargs={"pk": group_id, "milestone_id": milestone_id},
        )
        response = self.student_client.post(add_task_url, {"name": "Share literature review"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task_id = response.json()["id"]

        # Student completes task
        update_task_url = reverse(
            "groups:group-update-task",
            kwargs={"pk": group_id, "task_id": task_id},
        )
        response = self.student_client.put(update_task_url, {"completed": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["task"]["completed"])

