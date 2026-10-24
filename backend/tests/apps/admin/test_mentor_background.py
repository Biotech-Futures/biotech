"""Mentor background is one of five categories (AM2), and older values survive."""
import importlib

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AreasOfInterest, MentorProfile, User, UserInterest
from apps.users.models.admin_scope import AdminScope
from apps.users.models.mentor_profile import MENTOR_BACKGROUND_ERROR, normalize_mentor_background

migration = importlib.import_module("apps.users.migrations.0024_normalize_mentor_background")

# As main's 0041_mentor_background_labels settled them. Note the en dash:
# the hyphen spelling below is the pre-0041 label, which the migration
# still maps for stored data but is no longer an accepted input.
CATEGORIES = [
    "Academic",
    "Industry",
    "University Student – Undergraduate",
    "University Student – Postgraduate",
    "University Student – HDR",
]
KEYS = ["academic", "industry", "undergraduate", "postgraduate", "hdr"]


class MentorBackgroundChoicesTests(SimpleTestCase):
    def test_exactly_five_categories_in_order(self):
        self.assertEqual(MentorProfile.BackgroundChoices.labels, CATEGORIES)
        self.assertEqual(MentorProfile.BackgroundChoices.values, KEYS)

    def test_normalizes_keys_and_labels_in_any_case(self):
        for label, key in zip(CATEGORIES, KEYS):
            for value in (key, label, label.upper(), f"  {label}  "):
                self.assertEqual(normalize_mentor_background(value), key, value)

    def test_blank_means_not_set(self):
        for value in (None, "", "   "):
            self.assertIsNone(normalize_mentor_background(value))

    def test_rejects_anything_else(self):
        # "University Student - HDR" uses a hyphen: that is the pre-0041 label,
        # which the data migration still maps but is no longer a valid input.
        for value in ("Research", "HDR candidate", "University Student - HDR", 5, ["hdr"]):
            with self.assertRaisesMessage(ValueError, MENTOR_BACKGROUND_ERROR):
                normalize_mentor_background(value)
        # The message names the labels, so it follows them rather than being
        # spelled out twice.
        self.assertEqual(
            MENTOR_BACKGROUND_ERROR,
            "Mentor background must be one of: " + ", ".join(CATEGORIES),
        )


class MentorBackgroundMigrationTests(TestCase):
    def make_mentor(self, email, background):
        user = User.objects.create_user(email=email, password="testpass")
        # The column has never been constrained, so legacy free text exists.
        return MentorProfile.objects.create(
            user=user, institution="Uni", mentor_reason="Help", background=background,
        )

    def test_maps_only_unambiguous_values_and_keeps_the_rest(self):
        cases = {
            "industry": "industry",
            " Postgraduate ": "postgraduate",
            "HDR": "hdr",
            "ACADEMIC": "academic",
            "University Student - Undergraduate": "undergraduate",
            "university student - postgraduate ": "postgraduate",
            "University Student - HDR": "hdr",
            "": None,
            "   ": None,
            None: None,
            # Not guessed: left exactly as stored for an admin to review.
            "Research": "Research",
            "Seed mentor background.": "Seed mentor background.",
            "HDR candidate": "HDR candidate",
            "Undergraduate student": "Undergraduate student",
            "PhD": "PhD",
        }
        profiles = {
            stored: self.make_mentor(f"mentor{index}@example.com", stored)
            for index, stored in enumerate(cases)
        }

        migration.normalize_backgrounds(apps, None)

        for stored, expected in cases.items():
            profiles[stored].refresh_from_db()
            self.assertEqual(profiles[stored].background, expected, repr(stored))

    def test_running_twice_changes_nothing_more(self):
        profile = self.make_mentor("again@example.com", " HDR ")
        migration.normalize_backgrounds(apps, None)
        migration.normalize_backgrounds(apps, None)
        profile.refresh_from_db()
        self.assertEqual(profile.background, "hdr")


class AdminMentorBackgroundApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password="testpass")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.interest = AreasOfInterest.objects.create(interest_desc="Genetics")

    def mentor_payload(self, email, **extra):
        return {
            "email": email,
            "firstName": "Mia",
            "lastName": "Mentor",
            "role": "mentor",
            "country": "Australia",
            "mentorInstitution": "University of Sydney",
            "mentorReason": "Support students",
            "mentorMaxGroupCount": 2,
            "interests": ["Genetics"],
            **extra,
        }

    def make_mentor(self, background):
        user = User.objects.create_user(
            email="existing@example.com", password="testpass", first_name="Old", last_name="Name",
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=Roles.objects.get_or_create(role_name="mentor")[0], valid_from=timezone.now(),
        )
        profile = MentorProfile.objects.create(
            user=user, institution="Uni", mentor_reason="Help", background=background, max_group_count=2,
        )
        UserInterest.objects.create(user=user, interest=self.interest)
        return profile

    def update(self, profile, payload):
        return self.client.put(f"/api/v1/admin/user/{profile.user_id}/", payload, format="json")

    def background_of(self, email):
        return MentorProfile.objects.get(user__email=email).background

    # -- Create --------------------------------------------------------------

    def test_create_accepts_each_category_and_stores_its_key(self):
        for index, (label, key) in enumerate(zip(CATEGORIES, KEYS)):
            email = f"new{index}@example.com"
            response = self.client.post(
                "/api/v1/admin/user/", self.mentor_payload(email, mentorBackground=label), format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(self.background_of(email), key)

    def test_create_without_a_background_leaves_it_unset(self):
        for index, extra in enumerate(({}, {"mentorBackground": None}, {"mentorBackground": "  "})):
            email = f"blank{index}@example.com"
            response = self.client.post("/api/v1/admin/user/", self.mentor_payload(email, **extra), format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertIsNone(self.background_of(email))

    def test_create_rejects_an_unknown_background_and_creates_nothing(self):
        response = self.client.post(
            "/api/v1/admin/user/", self.mentor_payload("bad@example.com", mentorBackground="Research"), format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["msg"], MENTOR_BACKGROUND_ERROR)
        self.assertFalse(User.objects.filter(email="bad@example.com").exists())

    def test_bulk_import_skips_only_the_row_with_an_unknown_background(self):
        response = self.client.post(
            "/api/v1/admin/user/bulk/",
            [
                self.mentor_payload("good@example.com", mentorBackground="hdr"),
                self.mentor_payload("bad@example.com", mentorBackground="HDR candidate"),
            ],
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            response.data["data"]["skipped"],
            [{"email": "bad@example.com", "reason": MENTOR_BACKGROUND_ERROR}],
        )
        self.assertEqual(self.background_of("good@example.com"), "hdr")
        self.assertFalse(User.objects.filter(email="bad@example.com").exists())

    # -- Update --------------------------------------------------------------

    def test_update_sets_a_category(self):
        profile = self.make_mentor("industry")
        self.assertEqual(self.update(profile, {"mentorBackground": "HDR"}).status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.background, "hdr")

    def test_update_rejects_an_unknown_background_without_other_edits(self):
        profile = self.make_mentor("industry")
        response = self.update(profile, {"firstName": "New", "mentorBackground": "Research"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["msg"], MENTOR_BACKGROUND_ERROR)
        profile.refresh_from_db()
        profile.user.refresh_from_db()
        self.assertEqual(profile.background, "industry")
        self.assertEqual(profile.user.first_name, "Old")

    def test_unrelated_edits_keep_the_stored_background(self):
        for stored in ("postgraduate", "Seed mentor background.", None):
            with self.subTest(stored=stored):
                profile = self.make_mentor(stored)
                response = self.update(profile, {"firstName": "New", "mentorInstitution": "UNSW"})
                self.assertEqual(response.status_code, 200, response.data)
                profile.refresh_from_db()
                self.assertEqual(profile.background, stored)
                self.assertEqual(profile.institution, "UNSW")
                profile.user.delete()

    def test_resending_an_unchanged_legacy_background_keeps_it(self):
        # The admin form sends the stored value back with every save.
        profile = self.make_mentor("Seed mentor background.")
        response = self.update(profile, {"firstName": "New", "mentorBackground": "Seed mentor background."})
        self.assertEqual(response.status_code, 200, response.data)
        profile.refresh_from_db()
        self.assertEqual(profile.background, "Seed mentor background.")
        self.assertEqual(profile.user.first_name, "New")

    def test_a_legacy_background_can_only_change_to_a_category_or_blank(self):
        profile = self.make_mentor("Research")
        self.assertEqual(self.update(profile, {"mentorBackground": "Science"}).status_code, 400)
        profile.refresh_from_db()
        self.assertEqual(profile.background, "Research")

        self.assertEqual(self.update(profile, {"mentorBackground": "Academic"}).status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.background, "academic")

    def test_update_can_clear_the_background(self):
        for cleared in (None, ""):
            with self.subTest(cleared=cleared):
                profile = self.make_mentor("industry")
                self.assertEqual(self.update(profile, {"mentorBackground": cleared}).status_code, 200)
                profile.refresh_from_db()
                self.assertIsNone(profile.background)
                profile.user.delete()
