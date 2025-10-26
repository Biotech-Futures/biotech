from django.urls import reverse
from rest_framework import status

from chat.models import Message
from groups.models import Group

from .base import AuthenticatedAPITestCase


class ChatEndpointsTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.student = self.create_student("chat.student@example.com")
        self.mentor = self.create_user("chat.mentor@example.com", role="mentor", status="active")
        self.group = self.create_group(
            group_id="BTF010",
            mentor=self.mentor.user,
            members=[self.student.user],
        )
        Message.objects.create(group=self.group, author=self.student.user, text="Hello team")

    def test_list_messages_requires_membership(self):
        url = reverse("chat:group-messages", kwargs={"group_id": self.group.pk})

        outsider = self.create_student("noaccess@example.com")
        self.authenticate(outsider.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.student.user)
        response = self.client.get(url, {"limit": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["messages"][0]["text"], "Hello team")

    def test_invalid_limit_returns_validation_error(self):
        url = reverse("chat:group-messages", kwargs={"group_id": self.group.pk})
        self.authenticate(self.student.user)
        response = self.client.get(url, {"limit": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", response.json())

    def test_create_message_with_attachments(self):
        url = reverse("chat:group-messages", kwargs={"group_id": self.group.pk})
        self.authenticate(self.student.user)

        payload = {
            "text": "Here is the file",
            "attachments": [
                {
                    "url": "https://cdn.example.com/uploads/diagram.png",
                    "filename": "diagram.png",
                    "size": 1024,
                    "mimeType": "image/png",
                }
            ],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["attachments"][0]["filename"], "diagram.png")

