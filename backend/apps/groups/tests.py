from django.test import TestCase
from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps
from .models import Groups, GroupMembers, CountryStates, Tracks
from datetime import timedelta

from .models import Countries

class CountriesApiTests(TestCase):
    

    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse('countries-list')
        self.admin_user = get_user_model().objects.create_user(
            email="myemail1@gmail.com", password='adminpass', is_staff=True
        )
        self.normal_user = get_user_model().objects.create_user(
            email="myemail2@gmail.com", password='userpass', is_staff=False
        )
        self.country1 = Countries.objects.create(country_name='Australia')
        self.country2 = Countries.objects.create(country_name='Brazil')

    def test_list_countries_anyone(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertIn('Australia', [c['country_name'] for c in response.data])

    def test_retrieve_country_anyone(self):
        url = reverse('countries-detail', args=[self.country1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country_name'], 'Australia')

    def test_create_country_admin_only(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.list_url, {'country_name': 'Global'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Countries.objects.filter(
            country_name='Global').exists())

    def test_create_country_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(self.list_url, {'country_name': 'RANDOM_COUNTRY'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(
            country_name='RANDOM_COUNTRY').exists())

    def test_create_country_unauthenticated_forbidden(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.list_url, {'country_name': 'Japan'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(
            country_name='Japan').exists())

class GroupMemberApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="admin@test.com", password="adminpass", is_staff=True
        )
        self.normal_user = get_user_model().objects.create_user(
            email="user@test.com", password="userpass", is_staff=False
        )

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="Track 1", state=self.state)
        safe_created_at = timezone.now() - timedelta(days=1) 
        self.group = Groups.objects.create(
            group_name="Test Group", 
            track=self.track,
            creation_datetime=safe_created_at)
        self.member1 = GroupMembers.objects.create(
            user=self.normal_user, group=self.group
        )
        self.member2 = GroupMembers.objects.create(
            user=self.admin_user, group=self.group
        )
        self.list_url = reverse("group-members-list")
        self.by_group_url = reverse("group-members-by-group", args=[self.group.id])

    def test_list_group_members_authenticated(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_group_members_unauthenticated(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_group_member_authenticated(self):
        self.client.force_authenticate(user=self.normal_user)
        url = reverse("group-members-detail", args=[self.member1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.member1.id)

    def test_retrieve_group_member_unauthenticated(self):
        self.client.logout()
        url = reverse("group-members-detail", args=[self.member1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_group_member_admin_only(self):
        self.client.force_authenticate(user=self.admin_user)
        new_user = get_user_model().objects.create_user(
            email="newuser@test.com", password="newpass", is_staff=False
        )
        response = self.client.post(
            self.list_url,
            {"user": new_user.id, "group": self.group.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_group_member_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(
            self.list_url,
            {"user": self.normal_user.id, "group": self.group.id}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_by_group_action_authenticated(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.by_group_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(m["group"] == self.group.id for m in response.data))

    def test_by_group_action_unauthenticated(self):
        self.client.logout()
        response = self.client.get(self.by_group_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)