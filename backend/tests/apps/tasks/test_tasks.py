from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.tasks.services import calculate_completion_rate, get_current_week_label


class CalculateCompletionRateTests(TestCase):
    def test_normal_case(self):
        self.assertEqual(calculate_completion_rate(3, 7), 42)

    def test_zero_total_returns_zero(self):
        self.assertEqual(calculate_completion_rate(0, 0), 0)

    def test_all_completed(self):
        self.assertEqual(calculate_completion_rate(5, 5), 100)

    def test_none_completed(self):
        self.assertEqual(calculate_completion_rate(0, 10), 0)

    def test_floors_fractional_result(self):
        # 1/3 * 100 = 33.33 -> floors to 33
        self.assertEqual(calculate_completion_rate(1, 3), 33)


class GetCurrentWeekLabelTests(TestCase):
    def test_first_week(self):
        created_at = timezone.now() - timedelta(days=3)
        self.assertEqual(get_current_week_label(created_at), "Week 1")

    def test_second_week(self):
        created_at = timezone.now() - timedelta(days=10)
        self.assertEqual(get_current_week_label(created_at), "Week 2")

    def test_exact_week_boundary(self):
        created_at = timezone.now() - timedelta(days=14)
        self.assertEqual(get_current_week_label(created_at), "Week 3")

    def test_same_day_is_week_one(self):
        created_at = timezone.now()
        self.assertEqual(get_current_week_label(created_at), "Week 1")
