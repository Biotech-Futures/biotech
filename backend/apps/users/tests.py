from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.groups.models import Countries, CountryStates, Tracks
from apps.users.models import User
from apps.users.serializers import UserSerializer


class UserGeographyTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.nsw = CountryStates.objects.create(country=country, state_name="NSW")
        self.vic = CountryStates.objects.create(country=country, state_name="VIC")
        self.nsw_track = Tracks.objects.create(track_name="AUS-NSW", state=self.nsw)
        self.vic_track = Tracks.objects.create(track_name="AUS-VIC", state=self.vic)

    def test_state_is_derived_from_track(self):
        user = User.objects.create_user(
            email="derived-state@example.com",
            first_name="Derived",
            last_name="State",
            track=self.nsw_track,
        )

        self.assertEqual(user.state_id, self.nsw.id)
        self.assertEqual(user.state, self.nsw)

    def test_state_changes_when_track_changes(self):
        user = User.objects.create_user(
            email="track-swap@example.com",
            first_name="Track",
            last_name="Swap",
            track=self.nsw_track,
        )

        user.track = self.vic_track
        user.save(update_fields=["track"])
        user.refresh_from_db()

        self.assertEqual(user.state_id, self.vic.id)
        self.assertEqual(user.state, self.vic)

    def test_state_is_none_without_track(self):
        user = User.objects.create_user(
            email="no-track@example.com",
            first_name="No",
            last_name="Track",
        )

        self.assertIsNone(user.state_id)
        self.assertIsNone(user.state)

    def test_user_model_no_longer_has_state_field(self):
        with self.assertRaises(FieldDoesNotExist):
            User._meta.get_field("state")


class MustChangePasswordFlagTests(TestCase):
    """Contract test for the `must_change_password` field on `UserSerializer`.

    The FE relies on this flag (returned from `/api/v1/users/me/`) to decide
    whether to route a freshly logged-in user into the password set/change flow
    before letting them into the dashboard. It MUST be:

      * True  — for users that still need to complete password setup
                (admin-invited users start in this state because
                `User.objects.create_user(..., password=None)` calls
                `set_unusable_password()`).
      * False — once any code path successfully sets a password
                (`AdminSetPasswordView`, `confirm_password_reset`, etc.).
    """

    def _serialize(self, user):
        return UserSerializer(user).data

    def test_invited_user_must_change_password(self):
        user = User.objects.create_user(
            email="invited@example.com",
            first_name="Invited",
            last_name="User",
        )
        self.assertFalse(user.has_usable_password())
        self.assertTrue(self._serialize(user)["must_change_password"])

    def test_user_with_password_does_not_need_to_change(self):
        user = User.objects.create_user(
            email="active@example.com",
            first_name="Active",
            last_name="User",
            password="aV3rySecret!",
        )
        self.assertTrue(user.has_usable_password())
        self.assertFalse(self._serialize(user)["must_change_password"])

    def test_flag_flips_false_after_set_password(self):
        user = User.objects.create_user(
            email="postset@example.com",
            first_name="Post",
            last_name="Set",
        )
        self.assertTrue(self._serialize(user)["must_change_password"])

        user.set_password("freshSecret!42")
        user.save(update_fields=["password"])

        self.assertFalse(self._serialize(user)["must_change_password"])

    def test_flag_flips_true_again_if_password_invalidated(self):
        # Defensive: if an admin ever explicitly unusable-passwords a user
        # (e.g. to force re-onboarding) the flag should reflect that.
        user = User.objects.create_user(
            email="recycle@example.com",
            first_name="Re",
            last_name="Cycle",
            password="initialSecret!1",
        )
        self.assertFalse(self._serialize(user)["must_change_password"])

        user.set_unusable_password()
        user.save(update_fields=["password"])

        self.assertTrue(self._serialize(user)["must_change_password"])

    def test_me_endpoint_includes_must_change_password(self):
        user = User.objects.create_user(
            email="me@example.com",
            first_name="Me",
            last_name="User",
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse("MeListHTMLView"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("must_change_password", response.data)
        self.assertTrue(response.data["must_change_password"])

        user.set_password("now-i-have-one!")
        user.save(update_fields=["password"])
        # Re-auth because set_password rotates the session hash.
        client.force_authenticate(user=user)
        response = client.get(reverse("MeListHTMLView"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["must_change_password"])
