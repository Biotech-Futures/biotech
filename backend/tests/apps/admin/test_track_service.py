"""Tests for admin track service (create, archive, restore, list, list_states)."""
from django.test import TestCase

from apps.admin.services.track import (
    list_tracks, create_track, archive_track, restore_track, list_states,
)
from apps.groups.models import Countries, CountryStates, Tracks
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope


class TrackServiceTests(TestCase):
    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)

        self.global_admin = User.objects.create_user(
            email="global@example.com", first_name="Global", last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.global_admin, is_global=True)

        self.track_admin = User.objects.create_user(
            email="track@example.com", first_name="Track", last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.track_admin, track=self.track, is_global=False)

    def test_list_tracks_global_admin(self):
        result = list_tracks(requesting_user=self.global_admin)
        names = [t["trackName"] for t in result["data"]]
        self.assertIn("AUS-NSW", names)

    def test_list_tracks_track_admin(self):
        result = list_tracks(requesting_user=self.track_admin)
        names = [t["trackName"] for t in result["data"]]
        self.assertEqual(names, ["AUS-NSW"])

    def test_list_tracks_excludes_archived_by_default(self):
        archived = Tracks.objects.create(track_name="ARCHIVED", state=self.state)
        archived.is_archived = True
        archived.save()
        result = list_tracks(requesting_user=self.global_admin)
        names = [t["trackName"] for t in result["data"]]
        self.assertIn("AUS-NSW", names)
        self.assertNotIn("ARCHIVED", names)

    def test_list_tracks_includes_archived_when_requested(self):
        archived = Tracks.objects.create(track_name="ARCHIVED", state=self.state)
        archived.is_archived = True
        archived.save()
        result = list_tracks(requesting_user=self.global_admin, include_archived=True)
        names = [t["trackName"] for t in result["data"]]
        self.assertIn("ARCHIVED", names)

    def test_create_track_global_admin(self):
        result = create_track(
            {"track_name": "NZ-AKL", "state_id": self.state.id},
            requesting_user=self.global_admin,
        )
        self.assertEqual(result["msg"], "Track created successfully")
        self.assertEqual(result["data"]["trackName"], "NZ-AKL")

    def test_create_track_track_admin_forbidden(self):
        result = create_track(
            {"track_name": "NZ-AKL", "state_id": self.state.id},
            requesting_user=self.track_admin,
        )
        self.assertEqual(result["msg"], "Only global admins can create tracks")
        self.assertIsNone(result["data"])

    def test_create_track_invalid_state(self):
        result = create_track(
            {"track_name": "INVALID", "state_id": 9999},
            requesting_user=self.global_admin,
        )
        self.assertEqual(result["msg"], "Invalid state")

    def test_create_track_duplicate_name(self):
        result = create_track(
            {"track_name": "AUS-NSW", "state_id": self.state.id},
            requesting_user=self.global_admin,
        )
        self.assertEqual(result["msg"], "Track name already exists")

    def test_create_track_missing_name(self):
        result = create_track(
            {"state_id": self.state.id},
            requesting_user=self.global_admin,
        )
        self.assertEqual(result["msg"], "Track name is required")

    def test_create_track_missing_state(self):
        result = create_track(
            {"track_name": "NEW-TRACK"},
            requesting_user=self.global_admin,
        )
        self.assertEqual(result["msg"], "State is required")

    def test_archive_track(self):
        result = archive_track(self.track.id, requesting_user=self.global_admin)
        self.assertEqual(result["msg"], "Track archived successfully")
        self.track.refresh_from_db()
        self.assertTrue(self.track.is_archived)

    def test_archive_track_track_admin_forbidden(self):
        result = archive_track(self.track.id, requesting_user=self.track_admin)
        self.assertEqual(result["msg"], "Only global admins can archive tracks")

    def test_archive_track_not_found(self):
        result = archive_track(9999, requesting_user=self.global_admin)
        self.assertEqual(result["msg"], "Track not found")

    def test_restore_track(self):
        self.track.is_archived = True
        self.track.save()
        result = restore_track(self.track.id, requesting_user=self.global_admin)
        self.assertEqual(result["msg"], "Track restored successfully")
        self.track.refresh_from_db()
        self.assertFalse(self.track.is_archived)

    def test_restore_track_track_admin_forbidden(self):
        result = restore_track(self.track.id, requesting_user=self.track_admin)
        self.assertEqual(result["msg"], "Only global admins can restore tracks")

    def test_restore_track_not_found(self):
        result = restore_track(9999, requesting_user=self.global_admin)
        self.assertEqual(result["msg"], "Track not found")

    def test_list_states(self):
        result = list_states()
        self.assertIn("data", result)
        self.assertGreaterEqual(len(result["data"]), 1)
        state_names = [s["stateName"] for s in result["data"]]
        self.assertIn("NSW", state_names)
