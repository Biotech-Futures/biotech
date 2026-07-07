from datetime import timedelta

from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import Countries, CountryStates
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    AreasOfInterest,
    StudentProfile,
    SupervisorProfile,
    User,
    UserInterest,
)
from apps.users.serializers import UserSerializer


class UserGeographyTests(TestCase):
    """Geography now lives on ``User.state`` (a direct FK to
    ``groups.CountryStates``). The old track model and the derived state it
    used to imply were removed, so these tests assert the user's state can be
    set/reassigned directly and that the model shape reflects the migration
    (``state`` FK present, the former geography field gone)."""

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.nsw = CountryStates.objects.create(country=country, state_name="NSW")
        self.vic = CountryStates.objects.create(country=country, state_name="VIC")

    def test_state_can_be_assigned(self):
        user = User.objects.create_user(
            email="assigned-state@example.com",
            first_name="Assigned",
            last_name="State",
            state=self.nsw,
        )

        self.assertEqual(user.state_id, self.nsw.id)
        self.assertEqual(user.state, self.nsw)

    def test_state_can_be_reassigned(self):
        user = User.objects.create_user(
            email="state-swap@example.com",
            first_name="State",
            last_name="Swap",
            state=self.nsw,
        )

        user.state = self.vic
        user.save(update_fields=["state"])
        user.refresh_from_db()

        self.assertEqual(user.state_id, self.vic.id)
        self.assertEqual(user.state, self.vic)

    def test_state_is_none_without_geography(self):
        user = User.objects.create_user(
            email="no-state@example.com",
            first_name="No",
            last_name="State",
        )

        self.assertIsNone(user.state_id)
        self.assertIsNone(user.state)

    def test_user_model_has_state_fk_and_no_track_field(self):
        # ``state`` is now a real FK to CountryStates ...
        state_field = User._meta.get_field("state")
        self.assertEqual(state_field.related_model, CountryStates)
        # ... and the retired ``track`` field is gone.
        with self.assertRaises(FieldDoesNotExist):
            User._meta.get_field("track")


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


class ProfilePageFieldsTests(TestCase):
    """Contract tests for the new read-only profile fields surfaced by
    `UserSerializer` (and therefore `/api/v1/users/me/`):

      * `interests` — list of the user's selected areas of interest.
      * `supervisor_name` / `supervisor_email` — populated for students from
        their linked SupervisorProfile.user.
      * `supervisor_school_name` — populated for users currently in the
        supervisor role from their own SupervisorProfile.
    """

    @classmethod
    def setUpTestData(cls):
        # Role IDs are referenced by integer throughout the existing code
        # (e.g. `if rah.role_id == 4`). Mirror that here.
        cls.student_role = Roles.objects.create(pk=4, role_name="Student")
        cls.supervisor_role = Roles.objects.create(pk=2, role_name="Supervisor")

    def _assign_role(self, user, role):
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=now - timedelta(minutes=1),
            valid_to=now + timedelta(weeks=52),
        )

    def _make_student(self, *, email, supervisor_profile=None, school_name="Test High"):
        user = User.objects.create_user(
            email=email,
            first_name="Stu",
            last_name="Dent",
        )
        self._assign_role(user, self.student_role)
        StudentProfile.objects.create(
            user=user,
            pg_first_name="Pa",
            pg_last_name="Rent",
            parent_guardian_flag=True,
            supervisor=supervisor_profile,
            school_name=school_name,
            year_lvl="10",
        )
        return user

    def _make_supervisor(self, *, email, first_name, last_name, school_name):
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        self._assign_role(user, self.supervisor_role)
        return user, SupervisorProfile.objects.create(user=user, school_name=school_name)

    def _serialize(self, user):
        return UserSerializer(user).data

    def test_interests_returns_sorted_descriptions(self):
        user = User.objects.create_user(
            email="interested@example.com",
            first_name="In",
            last_name="Terested",
        )
        bio = AreasOfInterest.objects.create(interest_desc="Biology")
        chem = AreasOfInterest.objects.create(interest_desc="Chemistry")
        astro = AreasOfInterest.objects.create(interest_desc="Astrophysics")
        UserInterest.objects.create(user=user, interest=bio)
        UserInterest.objects.create(user=user, interest=chem)
        UserInterest.objects.create(user=user, interest=astro)

        data = self._serialize(user)
        self.assertEqual(
            data["interests"],
            ["Astrophysics", "Biology", "Chemistry"],
        )

    def test_interests_empty_list_when_user_has_none(self):
        user = User.objects.create_user(
            email="boring@example.com",
            first_name="No",
            last_name="Interests",
        )
        data = self._serialize(user)
        self.assertEqual(data["interests"], [])

    def test_student_sees_supervisor_name_and_email(self):
        _sup_user, sup_profile = self._make_supervisor(
            email="super@example.com",
            first_name="Super",
            last_name="Visor",
            school_name="Acme Academy",
        )
        student = self._make_student(
            email="student@example.com",
            supervisor_profile=sup_profile,
        )

        data = self._serialize(student)
        self.assertEqual(data["supervisor_name"], "Super Visor")
        self.assertEqual(data["supervisor_email"], "super@example.com")
        # Students themselves are not supervisors -> supervisor_school_name null.
        self.assertIsNone(data["supervisor_school_name"])

    def test_student_without_linked_supervisor_returns_null_supervisor_fields(self):
        student = self._make_student(
            email="orphan-student@example.com",
            supervisor_profile=None,
        )
        data = self._serialize(student)
        self.assertIsNone(data["supervisor_name"])
        self.assertIsNone(data["supervisor_email"])
        self.assertIsNone(data["supervisor_school_name"])

    def test_supervisor_sees_their_own_school_name(self):
        sup_user, _ = self._make_supervisor(
            email="myschool@example.com",
            first_name="Sue",
            last_name="Perv",
            school_name="River High",
        )
        data = self._serialize(sup_user)
        self.assertEqual(data["supervisor_school_name"], "River High")
        # The student-only fields stay null for a supervisor account.
        self.assertIsNone(data["supervisor_name"])
        self.assertIsNone(data["supervisor_email"])

    def test_non_student_non_supervisor_returns_null_for_all_supervisor_fields(self):
        # No role assignment at all -> all supervisor-related fields null,
        # interests defaults to empty list.
        user = User.objects.create_user(
            email="roleless@example.com",
            first_name="No",
            last_name="Role",
        )
        data = self._serialize(user)
        self.assertIsNone(data["supervisor_name"])
        self.assertIsNone(data["supervisor_email"])
        self.assertIsNone(data["supervisor_school_name"])
        self.assertEqual(data["interests"], [])

    def test_me_endpoint_exposes_new_profile_fields(self):
        _sup_user, sup_profile = self._make_supervisor(
            email="me-sup@example.com",
            first_name="My",
            last_name="Sup",
            school_name="Hilltop School",
        )
        student = self._make_student(
            email="me-student@example.com",
            supervisor_profile=sup_profile,
        )
        bio = AreasOfInterest.objects.create(interest_desc="Biology")
        UserInterest.objects.create(user=student, interest=bio)

        client = APIClient()
        client.force_authenticate(user=student)
        response = client.get(reverse("MeListHTMLView"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["interests"], ["Biology"])
        self.assertEqual(response.data["supervisor_name"], "My Sup")
        self.assertEqual(response.data["supervisor_email"], "me-sup@example.com")
        self.assertIsNone(response.data["supervisor_school_name"])
