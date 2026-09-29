"""The title a team submits with its entry: in the documents and on the
marking page. It's the submitted title, not a later draft."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.services.docx import project_title
from apps.submissions.models import Submission

from .fixtures import _GradingFixture


class ProjectTitleTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        # Submitted as "Plant Sensors", then a new draft title typed since.
        Submission.objects.filter(group=self.group).update(
            submitted_project_title="Plant Sensors", project_title="A Later Draft"
        )

    def _get(self, name, *args):
        r = self.client.get(reverse(name, args=args))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()

    def test_the_documents_use_the_submitted_title(self):
        self.assertEqual(project_title(self.group), "Plant Sensors")
        Submission.objects.filter(group=self.group).update(submitted_project_title="")
        self.assertEqual(project_title(self.group), "")

    def test_the_marking_page_carries_it(self):
        marking = self._get("grading:group-marking", self.group.id)
        self.assertEqual(marking["group"]["project_title"], "Plant Sensors")

    def test_a_team_without_an_entry_has_no_title(self):
        from apps.groups.models import Groups

        empty = Groups.objects.create(group_name="BTF-EMPTY")
        self.assertEqual(self._get("grading:group-marking", empty.id)["group"]["project_title"], "")
