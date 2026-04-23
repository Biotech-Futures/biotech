from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, APITestCase

from apps.groups.models import Countries, CountryStates, Groups, Tracks

from .filters import FlexibleDeletedFilter, MilestoneFilter, TaskFilter
from .models import Milestone, Tasks
from .views import MilestoneListHTMLView, TaskListHTMLView

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TaskFixture:
    """Minimal DB objects reused across test classes."""

    def _create_fixtures(self):
        self.user = User.objects.create_user(
            email="fix4@test.com", password="pass",
            first_name="Fix", last_name="Four",
        )
        country = Countries.objects.create(country_name="AU")
        state = CountryStates.objects.create(country=country, state_name="VIC")
        track = Tracks.objects.create(track_name="VIC-01", state=state)
        group = Groups.objects.create(group_name="G01", track=track)
        self.milestone = Milestone.objects.create(
            group=group, milestone_name="MS1",
        )
        self.active_task = Tasks.objects.create(
            task_name="Active", milestone=self.milestone,
            due_date=timezone.now() + timezone.timedelta(days=1),
        )
        self.deleted_task = Tasks.objects.create(
            task_name="Deleted", milestone=self.milestone,
            due_date=timezone.now() + timezone.timedelta(days=2),
            deleted_flag=True,
        )


# ---------------------------------------------------------------------------
# Layer 1 — pure unit tests for FlexibleDeletedFilter
# ---------------------------------------------------------------------------

class FlexibleDeletedFilterUnitTests(TestCase):
    """
    Tests FlexibleDeletedFilter.filter() in isolation — no HTTP, no views.

    Verifies three contract points:
      a) truthy variants   → deleted_flag=True
      b) falsy variants    → deleted_flag=False
      c) invalid strings   → raises ValidationError (would become HTTP 400)
    """

    def setUp(self):
        country = Countries.objects.create(country_name="AU2")
        state = CountryStates.objects.create(country=country, state_name="QLD")
        track = Tracks.objects.create(track_name="QLD-01", state=state)
        group = Groups.objects.create(group_name="G02", track=track)
        ms = Milestone.objects.create(group=group, milestone_name="MS2")
        Tasks.objects.create(
            task_name="Active", milestone=ms,
            due_date=timezone.now() + timezone.timedelta(days=1),
        )
        Tasks.objects.create(
            task_name="Deleted", milestone=ms,
            due_date=timezone.now() + timezone.timedelta(days=2),
            deleted_flag=True,
        )
        self.f = FlexibleDeletedFilter(field_name='deleted_flag')
        self.qs = Tasks.objects.all()

    # --- truthy variants → show only deleted rows ---

    def test_true_returns_deleted_only(self):
        result = self.f.filter(self.qs, 'true')
        self.assertTrue(all(t.deleted_flag is True for t in result))

    def test_True_capital_returns_deleted_only(self):
        result = self.f.filter(self.qs, 'True')
        self.assertTrue(all(t.deleted_flag is True for t in result))

    def test_1_returns_deleted_only(self):
        result = self.f.filter(self.qs, '1')
        self.assertTrue(all(t.deleted_flag is True for t in result))

    def test_yes_returns_deleted_only(self):
        result = self.f.filter(self.qs, 'yes')
        self.assertTrue(all(t.deleted_flag is True for t in result))

    # --- falsy variants → show only active rows ---

    def test_false_returns_active_only(self):
        result = self.f.filter(self.qs, 'false')
        self.assertTrue(all(t.deleted_flag is False for t in result))

    def test_False_capital_returns_active_only(self):
        result = self.f.filter(self.qs, 'False')
        self.assertTrue(all(t.deleted_flag is False for t in result))

    def test_0_returns_active_only(self):
        result = self.f.filter(self.qs, '0')
        self.assertTrue(all(t.deleted_flag is False for t in result))

    def test_no_returns_active_only(self):
        result = self.f.filter(self.qs, 'no')
        self.assertTrue(all(t.deleted_flag is False for t in result))

    # --- empty / None → no filter applied ---

    def test_none_value_returns_full_queryset(self):
        result = self.f.filter(self.qs, None)
        self.assertEqual(result.count(), self.qs.count())

    def test_empty_string_returns_full_queryset(self):
        result = self.f.filter(self.qs, '')
        self.assertEqual(result.count(), self.qs.count())

    # --- invalid values → ValidationError (HTTP 400 in the pipeline) ---

    def test_random_string_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.f.filter(self.qs, 'maybe')

    def test_numeric_string_out_of_range_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.f.filter(self.qs, '2')

    def test_gibberish_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.f.filter(self.qs, 'xyz')

    def test_validation_error_message_matches_spec(self):
        """Error detail must exactly match the spec: 'Invalid deleted value. Expected true or false.'"""
        try:
            self.f.filter(self.qs, 'random_string')
            self.fail("ValidationError not raised")
        except ValidationError as exc:
            self.assertIn('Invalid deleted value', str(exc.detail))


# ---------------------------------------------------------------------------
# Layer 2 — view-level tests via APIRequestFactory
# ---------------------------------------------------------------------------

class TaskListBooleanFilterViewTests(_TaskFixture, APITestCase):
    """Tests TaskListHTMLView through APIRequestFactory."""

    def setUp(self):
        self._create_fixtures()
        self.factory = APIRequestFactory()
        self.view = TaskListHTMLView.as_view()

    def _get(self, params=None):
        request = self.factory.get('/fake/', params or {})
        request.user = self.user
        return self.view(request)

    def _ids(self, response):
        return [r['id'] for r in response.data.get('results', response.data)]

    # --- falsy → active only ---

    def test_deleted_false_returns_active_only(self):
        response = self._get({'deleted': 'false'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertNotIn(self.deleted_task.id, ids)

    def test_deleted_0_returns_active_only(self):
        response = self._get({'deleted': '0'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    def test_deleted_no_returns_active_only(self):
        response = self._get({'deleted': 'no'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    def test_deleted_False_capital_returns_active_only(self):
        response = self._get({'deleted': 'False'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    # --- truthy → deleted only ---

    def test_deleted_true_returns_deleted_only(self):
        response = self._get({'deleted': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.deleted_task.id, ids)
        self.assertNotIn(self.active_task.id, ids)

    def test_deleted_1_returns_deleted_only(self):
        response = self._get({'deleted': '1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    def test_deleted_yes_returns_deleted_only(self):
        response = self._get({'deleted': 'yes'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    def test_deleted_True_capital_returns_deleted_only(self):
        response = self._get({'deleted': 'True'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    # --- invalid → HTTP 400, not 500 ---

    def test_invalid_value_returns_400(self):
        """Core regression: lowercase invalid value must return 400, not 500."""
        response = self._get({'deleted': 'random_string'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_value_error_message(self):
        response = self._get({'deleted': 'xyz'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid deleted value', str(response.data))

    # --- no param → all tasks returned ---

    def test_no_deleted_param_returns_all(self):
        response = self._get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertIn(self.deleted_task.id, ids)


class MilestoneListBooleanFilterViewTests(_TaskFixture, APITestCase):
    """Tests MilestoneListHTMLView through APIRequestFactory."""

    def setUp(self):
        self._create_fixtures()
        group = self.milestone.group
        self.deleted_milestone = Milestone.objects.create(
            group=group, milestone_name="Deleted MS",
            deleted_flag=True,
        )
        self.factory = APIRequestFactory()
        self.view = MilestoneListHTMLView.as_view()

    def _get(self, params=None):
        request = self.factory.get('/fake/', params or {})
        request.user = self.user
        return self.view(request)

    def _ids(self, response):
        return [r['id'] for r in response.data.get('results', response.data)]

    def test_deleted_false_excludes_soft_deleted_milestone(self):
        response = self._get({'deleted': 'false'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.milestone.id, ids)
        self.assertNotIn(self.deleted_milestone.id, ids)

    def test_deleted_true_returns_only_deleted_milestones(self):
        response = self._get({'deleted': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.deleted_milestone.id, ids)
        self.assertNotIn(self.milestone.id, ids)

    def test_invalid_value_returns_400(self):
        response = self._get({'deleted': 'bad_value'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
