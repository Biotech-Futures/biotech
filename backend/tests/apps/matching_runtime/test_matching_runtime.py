from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.users.models import MentorProfile

from apps.matching_runtime.models import MatchRecommendation, MatchRun


class MatchingRuntimeAdminWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="admin@matching.test",
            password="adminpass",
            is_staff=True,
        )
        self.old_mentor = get_user_model().objects.create_user(
            email="old-mentor@test.com",
            password="mentorpass",
        )
        self.new_mentor = get_user_model().objects.create_user(
            email="new-mentor@test.com",
            password="mentorpass",
        )
        MentorProfile.objects.create(
            user=self.old_mentor,
            institution="Uni",
            mentor_reason="Support",
            max_group_count=2,
        )
        MentorProfile.objects.create(
            user=self.new_mentor,
            institution="Uni",
            mentor_reason="Support",
            max_group_count=2,
        )

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-OPS", state=state)
        self.group = Groups.objects.create(group_name="Ops Group", track=self.track)
        self.existing_membership = GroupMembership.objects.create(
            group=self.group,
            user=self.old_mentor,
            membership_role="mentor",
        )
        self.match_run = MatchRun.objects.create(
            initiated_by_user=self.admin_user,
            track=self.track,
            run_type="reassignment",
        )
        self.recommendation = MatchRecommendation.objects.create(
            match_run=self.match_run,
            group=self.group,
            mentor_user=self.new_mentor,
            score="0.9500",
        )

    def test_bulk_accept_applies_recommendation_and_replaces_existing_mentor(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("match-recommendations-bulk-accept")
        response = self.client.post(
            url,
            {"recommendation_ids": [self.recommendation.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.recommendation.refresh_from_db()
        self.existing_membership.refresh_from_db()
        self.assertTrue(self.recommendation.accepted)
        self.assertIsNotNone(self.existing_membership.left_at)
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.new_mentor,
                membership_role="mentor",
                left_at__isnull=True,
            ).exists()
        )
