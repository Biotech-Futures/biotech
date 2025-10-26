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
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.users.models import StudentProfile, AreasOfInterest


class GroupsWithoutMentorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Users
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            email="admin_wo@test.com", password="adminpass", is_staff=True
        )
        self.normal_user = User.objects.create_user(
            email="user_wo@test.com", password="userpass", is_staff=False
        )

        # Geography and track
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(
            track_name="Bioinformatics", state=self.state)

        # Groups
        self.g1 = Groups.objects.create(group_name="G1", track=self.track)
        self.g2 = Groups.objects.create(group_name="G2", track=self.track)
        self.g3 = Groups.objects.create(group_name="G3", track=self.track)

        # Members and roles
        self.student1 = User.objects.create_user(
            email="s1@test.com", password="x")
        self.student2 = User.objects.create_user(
            email="s2@test.com", password="x")
        self.mentor_user = User.objects.create_user(
            email="m1@test.com", password="x")
        self.past_mentor_user = User.objects.create_user(
            email="m2@test.com", password="x")
        self.future_mentor_user = User.objects.create_user(
            email="m3@test.com", password="x")

        # Add memberships
        GroupMembers.objects.create(user=self.student1, group=self.g1)
        GroupMembers.objects.create(user=self.student2, group=self.g1)

        GroupMembers.objects.create(user=self.mentor_user, group=self.g2)

        GroupMembers.objects.create(user=self.past_mentor_user, group=self.g3)
        GroupMembers.objects.create(
            user=self.future_mentor_user, group=self.g3)

        # Roles
        self.mentor_role, _ = Roles.objects.get_or_create(role_name="Mentor")

        now = timezone.now()
        # Active mentor on g2
        RoleAssignmentHistory.objects.create(
            user=self.mentor_user,
            role=self.mentor_role,
            valid_from=now - timedelta(days=1),
            valid_to=None,
        )
        # Past mentor on g3 (ended)
        RoleAssignmentHistory.objects.create(
            user=self.past_mentor_user,
            role=self.mentor_role,
            valid_from=now - timedelta(days=10),
            valid_to=now - timedelta(days=1),
        )
        # Future mentor on g3 (not yet active)
        RoleAssignmentHistory.objects.create(
            user=self.future_mentor_user,
            role=self.mentor_role,
            valid_from=now + timedelta(days=1),
            valid_to=None,
        )

        self.url = reverse("groups-without-mentor")

    def test_without_mentor_requires_auth_and_admin(self):
        # Unauthenticated -> 401
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated non-admin -> 403
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_without_mentor_lists_only_groups_without_active_mentor(self):
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(self.url + "?page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        results = data["results"] if isinstance(
            data, dict) and "results" in data else data
        names = {row["group_name"] for row in results}

        # g2 has an active mentor member -> excluded
        self.assertNotIn("G2", names)
        # g1 has no mentor -> included
        self.assertIn("G1", names)
        # g3 has only past mentor and future mentor (not active) -> included
        self.assertIn("G3", names)

    def test_filters_track_and_region_and_cohort(self):
        self.client.force_authenticate(user=self.admin_user)
        # Region filter (NSW) should still include G1 and G3 and exclude G2
        resp = self.client.get(self.url + "?region=NSW&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json()["results"]
        names = {row["group_name"] for row in results}
        self.assertIn("G1", names)
        self.assertIn("G3", names)
        self.assertNotIn("G2", names)

        # Track filter by name (case-insensitive)
        resp = self.client.get(self.url + "?track=bioinformatics&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Cohort filter (use current year assumed by model defaults)
        year = timezone.now().year
        resp = self.client.get(self.url + f"?cohort_year={year}&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_track_filter_by_id_and_name_case_insensitive(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create another track and a group without mentor on it
        other_state = CountryStates.objects.create(
            country=self.country, state_name="VIC")
        other_track = Tracks.objects.create(
            track_name="Chemistry", state=other_state)
        g_other = Groups.objects.create(
            group_name="G_OTHER", track=other_track)

        # Filter by current track id -> should include g1/g3, exclude g_other
        resp = self.client.get(
            self.url + f"?track={self.track.id}&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertIn("G1", names)
        self.assertIn("G3", names)
        self.assertNotIn("G_OTHER", names)

        # Filter by track name (case-insensitive)
        resp = self.client.get(
            self.url + f"?track={self.track.track_name.lower()}&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertIn("G1", names)
        self.assertIn("G3", names)
        self.assertNotIn("G_OTHER", names)

    def test_region_filter_case_insensitive(self):
        self.client.force_authenticate(user=self.admin_user)
        # Another region with a group that should be excluded when filtering NSW
        other_country = Countries.objects.create(country_name="Australia")
        other_state = CountryStates.objects.create(
            country=other_country, state_name="VIC")
        other_track = Tracks.objects.create(
            track_name="Physics", state=other_state)
        Groups.objects.create(group_name="VIC_GROUP", track=other_track)

        # region case-insensitive should still include NSW groups only
        resp = self.client.get(self.url + "?region=nSw&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertIn("G1", names)
        self.assertIn("G3", names)
        self.assertNotIn("VIC_GROUP", names)

    def test_nonexistent_track_filter_returns_empty(self):
        self.client.force_authenticate(user=self.admin_user)
        # Use a very large track id that won't exist
        resp = self.client.get(self.url + "?track=999999&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        results = data["results"] if isinstance(
            data, dict) and "results" in data else data
        self.assertEqual(len(results), 0)

    def test_cohort_year_no_match_returns_empty(self):
        self.client.force_authenticate(user=self.admin_user)
        # Filter on a past year not used by default groups
        past_year = timezone.now().year - 5
        resp = self.client.get(
            self.url + f"?cohort_year={past_year}&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json()["results"]
        self.assertEqual(len(results), 0)

    def test_combined_filters_track_and_region(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create another region and track, with a group without mentor
        other_state = CountryStates.objects.create(
            country=self.country, state_name="QLD")
        other_track = Tracks.objects.create(
            track_name="Biotech-QLD", state=other_state)
        gq = Groups.objects.create(group_name="G_Q", track=other_track)
        # Combined filter on original track id and region NSW should exclude G_Q
        resp = self.client.get(
            self.url + f"?track={self.track.id}&region=NSW&page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertIn("G1", names)
        self.assertIn("G3", names)
        self.assertNotIn("G_Q", names)

    def test_excludes_deleted_groups(self):
        self.client.force_authenticate(user=self.admin_user)
        # Soft delete g1
        self.g1.deleted_flag = True
        self.g1.deleted_datetime = timezone.now()
        self.g1.save(update_fields=["deleted_flag", "deleted_datetime"])

        resp = self.client.get(self.url + "?page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertNotIn("G1", names)
        self.assertIn("G3", names)

    def test_mentor_in_another_group_does_not_exclude(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create a new group with no members
        g4 = Groups.objects.create(group_name="G4", track=self.track)
        # Create a mentor with active role not in g4
        mentor2 = get_user_model().objects.create_user(
            email="m2x@test.com", password="x")
        RoleAssignmentHistory.objects.create(
            user=mentor2,
            role=self.mentor_role,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=None,
        )
        # Do NOT add mentor2 to g4 members

        resp = self.client.get(self.url + "?page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row["group_name"] for row in resp.json()["results"]}
        self.assertIn("G4", names)

    def test_students_payload_contents(self):
        self.client.force_authenticate(user=self.admin_user)
        # Add student profiles for student1 and student2 (members of g1)
        interest = AreasOfInterest.objects.create(interest_desc="Biotech")
        StudentProfile.objects.create(
            user=self.student1,
            pg_first_name="PG",
            pg_last_name="One",
            parent_guardian_flag=True,
            school_name="School A",
            year_lvl="10",
            interest=interest,
        )
        StudentProfile.objects.create(
            user=self.student2,
            pg_first_name="PG",
            pg_last_name="Two",
            parent_guardian_flag=True,
            school_name="School B",
            year_lvl="11",
            interest=None,
        )
        # Add a member without StudentProfile; should be ignored in students list
        extra_user = get_user_model().objects.create_user(
            email="extra@test.com", password="x")
        GroupMembers.objects.create(user=extra_user, group=self.g1)

        resp = self.client.get(self.url + "?page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json()["results"]
        g1_row = next((r for r in results if r["group_name"] == "G1"), None)
        self.assertIsNotNone(g1_row)
        students = g1_row["students"]
        schools = {s["school"] for s in students}
        interests = {s["interest"] for s in students}
        self.assertIn("School A", schools)
        self.assertIn("School B", schools)
        self.assertIn("Biotech", interests)
        self.assertIn(None, interests)

    def test_pagination_shape(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create additional mentor-less groups to exceed default page size (10)
        for i in range(12):
            Groups.objects.create(group_name=f"PX{i}", track=self.track)

        # First page
        resp1 = self.client.get(self.url + "?page_size=5&page=1")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        data1 = resp1.json()
        self.assertIn("count", data1)
        self.assertIn("next", data1)
        self.assertIn("previous", data1)
        self.assertEqual(len(data1["results"]), 5)

        # Second page
        resp2 = self.client.get(self.url + "?page_size=5&page=2")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = resp2.json()
        self.assertEqual(len(data2["results"]), 5)
        self.assertIsNotNone(data1["next"])  # likely has next
        self.assertIsNone(data1["previous"])  # first page has no previous
        # second page should have previous
        self.assertIsNotNone(data2["previous"])

    def test_member_count_matches_membership(self):
        self.client.force_authenticate(user=self.admin_user)
        # g1 has two members
        resp = self.client.get(self.url + "?page_size=50")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json()["results"]
        g1_row = next((r for r in results if r["group_name"] == "G1"), None)
        self.assertIsNotNone(g1_row)
        self.assertEqual(g1_row["member_count"], 2)


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
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(
            track_name="Track 1", state=self.state)
        self.group1 = Groups.objects.create(
            group_name='Group One', track=self.track)

        self.create_group_data = {
            'group_name': 'team_alpha',
            'track': self.track.id
        }

    def make_deleted_group(self, name="Deleted Group"):
        # creation_datetime set here
        g = Groups.objects.create(group_name=name, track=self.track)
        g.deleted_flag = True
        g.deleted_datetime = timezone.now()
        g.save(update_fields=["deleted_flag", "deleted_datetime"])
        return g

    def test_list_groups_with_no_auth(self):
        url = reverse('groups-list')  # meaning /groups/
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_groups_normal_user(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(url)
        data = response.json()
        # Handle paginated response
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
        # Handle paginated response
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
        self.assertFalse(Groups.objects.filter(
            group_name="team_alpha").exists())

    def test_admin_can_create_group(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, self.create_group_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Groups.objects.filter(
            group_name='team_alpha', track=self.track).exists())

    def test_readonly_fields_ignored_on_create(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'group_name': 'team_beta',
            'track': self.track.id,
            'deleted_flag': True,
            'deleted_datetime': timezone.now().isoformat(),
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        obj = Groups.objects.get(group_name='team_beta', track=self.track)
        self.assertFalse(obj.deleted_flag)
        self.assertIsNone(obj.deleted_datetime)

    def test_duplicate_group_name_per_track_returns_400(self):
        url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        # first create
        resp1 = self.client.post(
            url, {'group_name': 'dup', 'track': self.track.id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        # duplicate (same track, same name)
        resp2 = self.client.post(
            url, {'group_name': 'dup', 'track': self.track.id}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', resp2.json())

    def test_update_requires_admin(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.patch(
            url, {'group_name': 'new_name'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Group One')

    def test_admin_can_patch_group_name(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            url, {'group_name': 'Renamed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Renamed')

    def test_retrieve_requires_auth(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # TODO only users who are part of the group or admin can see

    def test_retrieve_nonexistent_returns_404(self):
        url = reverse('groups-detail', args=['9999'])
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_rejects_unauthenticated(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.group1.refresh_from_db()
        self.assertFalse(self.group1.deleted_flag)

    def test_delete_rejects_non_admin(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        self.client.force_authenticate(self.normal_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.group1.refresh_from_db()
        self.assertFalse(self.group1.deleted_flag)

    def test_admin_soft_delete_hides_from_list(self):
        # admin can delete
        detail_url = reverse('groups-detail', args=[self.group1.group_number])
        list_url = reverse('groups-list')
        self.client.force_authenticate(user=self.admin_user)
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code,
                         status.HTTP_204_NO_CONTENT)

        # user can't see it
        self.client.force_authenticate(user=self.normal_user)
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        data = list_response.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = [row['id'] for row in data]
        self.assertNotIn(self.group1.id, ids)

        # should not pop up anymore
        get_response = self.client.get(detail_url)
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_staff_cannot_include_deleted_even_with_flag(self):
        deleted = self.make_deleted_group()
        url = reverse('groups-list') + '?include_deleted=true'
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = [row['id'] for row in data]
        self.assertNotIn(deleted.id, ids)

    def test_readonly_fields_ignored_on_update(self):
        url = reverse('groups-detail', args=[self.group1.group_number])
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.patch(url, {
            'group_name': 'Still Active',
            'deleted_flag': True,
            'deleted_datetime': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.group_name, 'Still Active')
        self.assertFalse(self.group1.deleted_flag)
        self.assertIsNone(self.group1.deleted_datetime)


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
        # Handle paginated response
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
        self.assertTrue(Countries.objects.filter(
            country_name='Global').exists())

    def test_create_country_unauthorised(self):
        response = self.client.post(
            self.list_url, {'country_name': "unauth_country"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Countries.objects.filter(
            country_name='unauth_country').exists())

    def test_create_country_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(
            self.list_url, {'country_name': 'RANDOM_COUNTRY'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(
            country_name='RANDOM_COUNTRY').exists())

    def test_create_country_unauthenticated_forbidden(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.list_url, {'country_name': 'Japan'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
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
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(
            track_name="Track 1", state=self.state)
        safe_created_at = timezone.now() - timedelta(days=1)
        self.group = Groups.objects.create(
            group_name="Test Group",
            track=self.track,
            # TODO: does setting creation_datetime to read_only impact this test
            creation_datetime=safe_created_at)
        self.member1 = GroupMembers.objects.create(
            user=self.normal_user, group=self.group
        )
        self.member2 = GroupMembers.objects.create(
            user=self.admin_user, group=self.group
        )
        self.list_url = reverse("group-members-list")
        self.by_group_url = reverse(
            "group-members-by-group", args=[self.group.id])

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
        self.assertTrue(
            all(m["group"] == self.group.id for m in response.data))

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
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(
            track_name="Track 1", state=self.state)
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


class RegisterStudentApiTests(TestCase):
    def setUp(self):
        from apps.groups.services.get_group_name import generate_group_name
        self.generate_group_name = generate_group_name

        self.client = APIClient()
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            email="admin_reg@test.com", password="adminpass", is_staff=True
        )
        self.normal_user = User.objects.create_user(
            email="user_reg@test.com", password="userpass", is_staff=False
        )

        # Geography and track setup for AU/NSW -> Track 'AUS-NSW'
        self.country = Countries.objects.create(
            country_name="Australia", country_name_SHORT_FORM="AUS")
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW", state_name_SHORT_FORM="NSW")
        self.track = Tracks.objects.create(
            track_name="AUS-NSW", state=self.state)

        self.url = reverse("groups-register-student")

    def payload(self, group_number="R_12345", email="student1@test.com"):
        # Minimal valid payload that passes register_user student flow
        return {
            "GroupNumber": group_number,
            "Title": email,
            "FirstName": "Stu",
            "Surname": "Dent",
            "GuardianName": "Parent",
            "GuardianSurname": "One",
            "GuardianEmail": "parent@test.com",
            "SupervisorFirstName": "Super",
            "SupervisorSurname": "Visor",
            "SupervisorEmail": "supervisor1@test.com",
            "Areaofinterest": "Chemistry",
            "SchoolName": "School A",
            "YearLevel": "10",
            "Country": "Australia",
            "Region": "NSW",
            "Created": f"{timezone.now().year}-03-01T12:00:00Z",
        }

    def test_requires_admin_and_required_fields(self):
        # Unauthenticated
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Non-admin
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Admin - missing fields -> 400 with keys
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertIn("group_number", body)
        self.assertIn("student_email", body)

    def test_create_group_user_membership_201_then_idempotent_200(self):
        self.client.force_authenticate(user=self.admin_user)
        p = self.payload(group_number="R_ABCDEF", email="stud1@example.com")

        # First call creates group, user, membership -> 201
        resp1 = self.client.post(self.url, p, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        data1 = resp1.json()
        self.assertTrue(data1.get("group_created"))
        self.assertTrue(data1.get("user_created"))
        self.assertTrue(data1.get("member_added"))
        # Group exists with correct number and track
        g = Groups.objects.get(group_number=p["GroupNumber"])
        self.assertEqual(g.track_id, self.track.id)
        # Student membership exists
        self.assertTrue(GroupMembers.objects.filter(
            group=g, user__email__iexact=p["Title"]).exists())

        # Second call (idempotent): user exists, membership exists -> 200
        resp2 = self.client.post(self.url, p, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = resp2.json()
        self.assertFalse(data2.get("group_created"))
        self.assertFalse(data2.get("member_added"))
        # user_created should be False on second call (existing user path)
        self.assertFalse(data2.get("user_created"))

        # Still only one membership
        self.assertEqual(
            GroupMembers.objects.filter(
                group=g, user__email__iexact=p["Title"]).count(),
            1,
        )

    def test_existing_user_branch_creates_membership_and_returns_flags(self):
        self.client.force_authenticate(user=self.admin_user)
        # Pre-create user so register_user goes through UserAlreadyExists branch
        User = get_user_model()
        existing = User.objects.create_user(
            email="preexist@test.com", password="x")
        p = self.payload(group_number="R_EXIST", email=existing.email)

        resp = self.client.post(self.url, p, format="json")
        # New group -> 201 even if user existed
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertTrue(data.get("group_created"))
        self.assertFalse(data.get("user_created"))
        self.assertTrue(data.get("member_added"))

    def test_auto_restore_deleted_group(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create a deleted group with a specific number
        year = timezone.now().year
        name = self.generate_group_name(self.track, year)
        g = Groups.objects.create(
            group_number="R_RESTORE",
            group_name=name,
            track=self.track,
            cohort_year=year,
            creation_datetime=timezone.now() - timedelta(days=1),
            deleted_flag=True,
            deleted_datetime=timezone.now(),
        )
        p = self.payload(group_number=g.group_number, email="auto1@test.com")
        resp = self.client.post(self.url, p, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        g.refresh_from_db()
        self.assertFalse(g.deleted_flag)
        self.assertIsNone(g.deleted_datetime)

    def test_auto_restore_conflict_name_clash_409(self):
        self.client.force_authenticate(user=self.admin_user)
        # Prepare a deleted group Gd and an active group Ga with the same (track, cohort, name)
        year = timezone.now().year
        name = self.generate_group_name(self.track, year)
        gd = Groups.objects.create(
            group_number="R_CONFLICT",
            group_name=name,
            track=self.track,
            cohort_year=year,
            creation_datetime=timezone.now() - timedelta(days=1),
            deleted_flag=True,
            deleted_datetime=timezone.now(),
        )
        ga = Groups.objects.create(
            group_number="R_ACTIVE",
            group_name=name,
            track=self.track,
            cohort_year=year,
        )
        # Now posting to restore gd should hit conflict
        p = self.payload(group_number=gd.group_number,
                         email="conflict@test.com")
        resp = self.client.post(self.url, p, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_bad_track_resolution_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)
        p = self.payload(group_number="R_BAD", email="bad@test.com")
        p.update({"Country": "Narnia"})
        resp = self.client.post(self.url, p, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        # Error should be keyed under Country per view's except mapping
        self.assertIn("Country", body)

    def test_bad_state_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)
        p = self.payload(group_number="R_BAD_STATE", email="badstate@test.com")
        p.update({"Region": "ZZZ"})
        resp = self.client.post(self.url, p, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        # Error should be keyed under State per view's except mapping
        self.assertIn("State", body)

    def test_existing_active_group_returns_200_group_created_false(self):
        self.client.force_authenticate(user=self.admin_user)
        # Pre-create active group with given number
        g = Groups.objects.create(
            group_number="R_EXIST2",
            group_name=self.generate_group_name(
                self.track, timezone.now().year),
            track=self.track,
            cohort_year=timezone.now().year,
        )
        p = self.payload(group_number=g.group_number,
                         email="activegroup@test.com")
        resp = self.client.post(self.url, p, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertFalse(data.get("group_created"))
        self.assertTrue(data.get("user_created"))
        self.assertTrue(data.get("member_added"))
