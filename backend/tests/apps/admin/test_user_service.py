from django.test import TestCase

from apps.admin.services.user import update_user
from apps.groups.models import Countries, CountryStates, Tracks
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import AdminProfile, User
from apps.users.models.admin_scope import AdminScope


class AdminUserServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.user = User.objects.create_user(
            email="supervisor@example.com",
            first_name="Chen",
            last_name="Supervisor",
            password="testpass",
        )

    def test_update_user_assigns_incoming_role_when_current_role_is_missing(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "track": None,
                "adminTracks": ["AUS-NSW"],
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertEqual(result["data"]["role"], "admin")
        self.assertEqual(result["data"]["adminTracks"], ["AUS-NSW"])
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(
                user=self.user,
                role__role_name="admin",
                valid_to__isnull=True,
            ).exists()
        )
        self.assertTrue(AdminProfile.objects.filter(admin=self.user).exists())
        self.assertTrue(
            AdminScope.objects.filter(user=self.user, track=self.track).exists()
        )

