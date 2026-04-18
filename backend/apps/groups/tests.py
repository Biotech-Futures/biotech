from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Groups, GroupMembership, CountryStates, Tracks, Countries


class GroupsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="myemail1@gmail.com", password='adminpass', is_staff=True
        )
        self.normal_user = get_user_model().objects.create_user(
            email="myemail2@gmail.com", password='userpass', is_staff=False
        )

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-1", state=self.state)
        self.group1 = Groups.objects.create(group_name='Group One', track=self.track)

        self.create_group_data = {
            'group_name': 'team_alpha',
            'track': self.track.id
        }

    def make_deleted_group(self, name="Deleted Group"):
        g = Groups.objects.create(group_name=name, track=self.track)
        g.deleted_at = timezone.now()
        g.save(update_fields=["deleted_at"])
        return g

    def test_list_groups_with_no_auth(self):
        url = reverse('groups-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_groups_normal_user(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(url)
        data = response.json()
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertIsInstance(data, list)
        self.assertTrue(any(row['id'] == self.group1.id for row in data))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_groups_normal_user_hides_deleted(self):
        url = reverse('groups-list')
        deleted_group = self.make_deleted_group()
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(url + "?include_deleted=true")
        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertIsInstance(data, list)
        self.assertFalse(any(row['id'] == deleted_group.id for row in data))
        self.assertTrue(any(row['id'] == self.group1.id for row in data))

    def test_list_groups_admin_user(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_group_with_no_auth(self):
        url = reverse('groups-list')
        response = self.client.post(url, self.create_group_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Groups.objects.filter(group_name="team_alpha").exists())

    def test_admin_can_create_group(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, self.create_group_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Groups.objects.filter(group_name='team_alpha', track=self.track).exists())

    def test_readonly_fields_ignored_on_create(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'group_name': 'team_beta',
            'track': self.track.id,
            'deleted_at': timezone.now().isoformat(),
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        obj = Groups.objects.get(group_name='team_beta', track=self.track)
        self.assertIsNone(obj.deleted_at)

    def test_duplicate_group_name_per_track_returns_400(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        resp1 = self.client.post(url, {'group_name': 'dup', 'track': self.track.id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        resp2 = self.client.post(url, {'group_name': 'dup', 'track': self.track.id}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', resp2.json())

    def test_update_requires_admin(self):
        url = reverse('groups-detail', args=[self.group1.id])
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.patch(url, {'group_name': 'new_name'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Group One')

    def test_admin_can_patch_group_name(self):
        url = reverse('groups-detail', args=[self.group1.id])
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(url, {'group_name': 'Renamed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Renamed')

    def test_retrieve_requires_auth(self):
        url = reverse('groups-detail', args=[self.group1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_nonexistent_returns_404(self):
        url = reverse('groups-detail', args=['9999'])
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_rejects_unauthenticated(self):
        url = reverse('groups-detail', args=[self.group1.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.group1.refresh_from_db()
        self.assertIsNone(self.group1.deleted_at)

    def test_delete_rejects_non_admin(self):
        url = reverse('groups-detail', args=[self.group1.id])
        self.client.force_authenticate(self.normal_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.group1.refresh_from_db()
        self.assertIsNone(self.group1.deleted_at)

    def test_admin_soft_delete_hides_from_list(self):
        detail_url = reverse('groups-detail', args=[self.group1.id])
        list_url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        self.client.force_authenticate(user=self.normal_user)
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        data = list_response.json()
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = [row['id'] for row in data]
        self.assertNotIn(self.group1.id, ids)

        get_response = self.client.get(detail_url)
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_staff_cannot_include_deleted_even_with_flag(self):
        deleted = self.make_deleted_group()
        url = reverse('groups-list') + '?include_deleted=true'
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = [row['id'] for row in data]
        self.assertNotIn(deleted.id, ids)

    def test_readonly_fields_ignored_on_update(self):
        url = reverse('groups-detail', args=[self.group1.id])
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.patch(url, {
            'group_name': 'Still Active',
            'deleted_at': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Still Active')
        self.assertIsNone(self.group1.deleted_at)

    def test_admin_can_bulk_create_groups_with_members(self):
        extra_user = get_user_model().objects.create_user(
            email="member@test.com", password="memberpass"
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("groups-bulk-create")
        response = self.client.post(
            url,
            {
                "groups": [
                    {
                        "group_name": "Bulk Group",
                        "track": self.track.id,
                        "member_user_ids": [extra_user.id],
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_group = Groups.objects.get(group_name="Bulk Group", track=self.track)
        self.assertTrue(
            GroupMembership.objects.filter(
                group=created_group,
                user=extra_user,
                left_at__isnull=True,
            ).exists()
        )

    def test_admin_can_bulk_add_and_remove_members(self):
        extra_user = get_user_model().objects.create_user(
            email="bulk-member@test.com", password="memberpass"
        )
        self.client.force_authenticate(user=self.admin_user)

        add_response = self.client.post(
            reverse("groups-add-members", args=[self.group1.id]),
            {"user_ids": [extra_user.id]},
            format="json",
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)
        membership = GroupMembership.objects.get(group=self.group1, user=extra_user, left_at__isnull=True)

        remove_response = self.client.post(
            reverse("groups-remove-members", args=[self.group1.id]),
            {"user_ids": [extra_user.id]},
            format="json",
        )
        self.assertEqual(remove_response.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertIsNotNone(membership.left_at)

    def test_admin_can_replace_group_mentor(self):
        old_mentor = get_user_model().objects.create_user(
            email="old-mentor@group.test",
            password="mentorpass",
        )
        new_mentor = get_user_model().objects.create_user(
            email="new-mentor@group.test",
            password="mentorpass",
        )
        from apps.users.models import MentorProfile

        MentorProfile.objects.create(user=old_mentor, institution="Uni", mentor_reason="Help", max_group_count=2)
        MentorProfile.objects.create(user=new_mentor, institution="Uni", mentor_reason="Help", max_group_count=2)
        existing_membership = GroupMembership.objects.create(
            group=self.group1,
            user=old_mentor,
            membership_role="mentor",
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("groups-replace-mentor", args=[self.group1.id]),
            {"mentor_user_id": new_mentor.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        existing_membership.refresh_from_db()
        self.assertIsNotNone(existing_membership.left_at)
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group1,
                user=new_mentor,
                membership_role="mentor",
                left_at__isnull=True,
            ).exists()
        )


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
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertEqual(len(data), 2)
        self.assertIn('Australia', [c['country_name'] for c in data])

    def test_retrieve_country_anyone(self):
        url = reverse('countries-detail', args=[self.country1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country_name'], 'Australia')

    def test_create_country_admin_only(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.list_url, {'country_name': 'Global'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Countries.objects.filter(country_name='Global').exists())

    def test_create_country_unauthorised(self):
        response = self.client.post(self.list_url, {'country_name': "unauth_country"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Countries.objects.filter(country_name='unauth_country').exists())

    def test_create_country_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(self.list_url, {'country_name': 'RANDOM_COUNTRY'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(country_name='RANDOM_COUNTRY').exists())

    def test_create_country_unauthenticated_forbidden(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.list_url, {'country_name': 'Japan'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Countries.objects.filter(country_name='Japan').exists())


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
        self.track = Tracks.objects.create(track_name="TRACK-1", state=self.state)
        self.group = Groups.objects.create(group_name="Test Group", track=self.track)
        self.member1 = GroupMembership.objects.create(user=self.normal_user, group=self.group)
        self.member2 = GroupMembership.objects.create(user=self.admin_user, group=self.group)
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
        new_user = get_user_model().objects.create_user(
            email="another@test.com", password="pass", is_staff=False
        )
        response = self.client.post(
            self.list_url,
            {"user": new_user.id, "group": self.group.id}
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


class TrackApiTests(TestCase):
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
        self.track = Tracks.objects.create(track_name="TRACK-1", state=self.state)
        self.list_url = reverse("tracks-list")
        self.detail_url = reverse("tracks-detail", args=[self.track.id])

    def test_list_tracks_authenticated(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_tracks_unauthenticated(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_track_authenticated(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_track_unauthenticated(self):
        self.client.logout()
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_track_admin_only(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            self.list_url,
            {"track_name": "TRACK-2", "state": self.state.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_track_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(
            self.list_url,
            {"track_name": "TRACK-2", "state": self.state.id}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_track_unauthenticated_forbidden(self):
        self.client.logout()
        response = self.client.post(
            self.list_url,
            {"track_name": "TRACK-2", "state": self.state.id}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
