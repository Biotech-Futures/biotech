from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase

from apps.groups.models import Countries, CountryStates, Tracks
from apps.users.models import User


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
