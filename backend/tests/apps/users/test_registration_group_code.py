"""A student creating a group sees its code while registering: numbers only,
apart from the group's name, held for them so they can save it and share it
with their teammates; the group takes it when it's registered."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupCodeReservation, GroupMembership, Groups
from apps.users.models import User
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

URL = "/api/v1/registration/group-code/"


class GroupCodeHoldTests(TestCase):
    def test_a_held_code_is_six_digits_and_not_the_groups_name(self):
        held = GroupCodeReservation.hold_new()
        self.assertRegex(held.code, r"^[1-9][0-9]{5}$")
        group = Groups.create_with_code(held.token)
        self.assertEqual(group.code, held.code)
        # Its name is still the usual BTF<n>.
        self.assertEqual(group.group_name, "BTF01")
        self.assertFalse(GroupCodeReservation.objects.exists())

    def test_naming_is_as_it_was(self):
        GroupCodeReservation.hold_new()
        self.assertEqual(Groups.create_auto_named().group_name, "BTF01")

    def test_an_expired_or_unknown_hold_gets_a_new_code(self):
        held = GroupCodeReservation.hold_new()
        held.expires_at = timezone.now() - timedelta(minutes=1)
        held.save(update_fields=["expires_at"])
        for token in (held.token, "nope", ""):
            with self.subTest(token=token):
                group = Groups.create_with_code(token)
                self.assertRegex(group.code, r"^[1-9][0-9]{5}$")
        self.assertEqual(len(set(Groups.objects.values_list("code", flat=True))), 3)

    def test_no_two_groups_share_a_code(self):
        codes = {Groups.create_with_code().code for _ in range(5)}
        self.assertEqual(len(codes), 5)

    def test_anyone_can_hold_a_code(self):
        response = APIClient().post(URL)
        self.assertEqual(response.status_code, 201)
        self.assertRegex(response.json()["code"], r"^[0-9]{6}$")
        self.assertTrue(response.json()["token"])


class StudentGroupCodeTests(MultiStudentSetup, TestCase):
    def test_a_student_group_is_registered_with_its_held_code(self):
        held = GroupCodeReservation.hold_new()
        body = batch("student_team")
        body["payload"]["group"]["codeToken"] = held.token
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["group_code"], held.code)
        self.assertEqual(Groups.objects.get(code=held.code).group_name, "BTF01")

    def test_without_a_held_code_the_group_still_gets_one(self):
        response = self.post_batch(batch("student_team"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(response.data["group_code"], r"^[0-9]{6}$")

    def test_a_supervisors_group_gets_no_code(self):
        response = self.post_batch(batch("supervisor_group"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("group_code", response.data)


class GroupMemberInterestTests(MultiStudentSetup, TestCase):
    def test_member_one_keeps_their_own_interests_apart_from_the_groups(self):
        from apps.users.models import UserInterest

        body = batch("student_team")
        body["payload"]["students"][0]["interests"] = ["Neuroscience & Mental Health Tech"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        creator = body["payload"]["students"][0]["email"]
        self.assertEqual(
            list(UserInterest.objects.filter(user__email=creator).values_list("interest__interest_desc", flat=True)),
            ["Neuroscience & Mental Health Tech"],
        )


class JoinGroupTests(MultiStudentSetup, TestCase):
    """A student given a group's code joins it at once, while it has room;
    a student's group may start with just them."""

    def registered_group(self, count=2):
        response = self.post_batch(batch("student_team", count))
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["group_code"]

    def joiner(self, code, *, offset=50, count=1):
        body = batch("student_team", count, offset=offset)
        body["payload"]["group"] = {"joinCode": code}
        # A joiner registers themselves: their own guardian, no teammates.
        body["payload"]["students"] = [
            batch("student_individual", offset=offset + index)["payload"]["students"][0] for index in range(count)
        ]
        return body

    def test_a_student_joins_a_registered_group_by_its_code(self):
        code = self.registered_group()
        response = self.post_batch(self.joiner(code))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["group_code"], code)
        group = Groups.objects.get(code=code)
        self.assertEqual(GroupMembership.objects.filter(group=group).count(), 3)
        self.assertTrue(
            GroupMembership.objects.filter(group=group, user__email="learner50@students.example.test").exists()
        )
        self.assertEqual(Groups.objects.count(), 1)

    def test_an_unknown_code_saves_nothing(self):
        response = self.post_batch(self.joiner("999999"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("group.joinCode", response.data["fields"])
        self.assertFalse(User.objects.filter(email="learner50@students.example.test").exists())

    def test_a_full_group_takes_no_one_else(self):
        code = self.registered_group(5)
        response = self.post_batch(self.joiner(code))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["fields"]["group.joinCode"], ["This group already has 5 members."])

    def test_joining_registers_only_the_student(self):
        code = self.registered_group()
        response = self.post_batch(self.joiner(code, count=2))
        self.assertEqual(response.status_code, 400)
        self.assertIn("students", response.data["fields"])

    def test_a_supervisors_group_isnt_joined_by_code(self):
        code = self.registered_group()
        body = batch("supervisor_group")
        body["payload"]["group"]["joinCode"] = code
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("group.joinCode", response.data["fields"])

    def test_a_student_may_start_a_group_alone(self):
        response = self.post_batch(batch("student_team", 1))
        self.assertEqual(response.status_code, 201, response.data)
        group = Groups.objects.get(code=response.data["group_code"])
        self.assertEqual(GroupMembership.objects.filter(group=group).count(), 1)

    def test_a_student_group_has_at_most_five(self):
        response = self.post_batch(batch("student_team", 6))
        self.assertEqual(response.status_code, 400)
        self.assertIn("students", response.data["fields"])

    def test_the_code_can_be_checked_before_registering(self):
        code = self.registered_group()
        found = APIClient().get(f"{URL}{code}/")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json(), {"code": code, "members": 2, "full": False})
        self.assertEqual(APIClient().get(f"{URL}999999/").status_code, 404)
        self.assertEqual(APIClient().get(f"{URL}abc/").status_code, 404)

    def test_a_student_group_needs_no_shared_interests(self):
        body = batch("student_team")
        body["payload"]["group"] = {}
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        body = batch("supervisor_group")
        body["payload"]["group"] = {}
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("group.interests", response.data["fields"])
