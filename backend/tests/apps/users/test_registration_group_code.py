"""A student creating a group sees its code while registering: numbers only,
apart from the group's name, held for them so they can save it and share it
with their teammates; the group takes it when it's registered."""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupCodeReservation, GroupMembership, Groups
from apps.users.models import RegistrationWindow, User
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


class GroupCodeExpiryTests(TestCase):
    """A held code lasts until registration ends, so the code a student
    shares is still their group's when they come back to register it."""

    def setUp(self):
        cache.clear()
        self.year = timezone.now().year

    def hold(self):
        response = APIClient().post(URL)
        self.assertEqual(response.status_code, 201)
        return GroupCodeReservation.objects.get(code=response.json()["code"])

    def test_a_held_code_lasts_until_registration_closes(self):
        closes = timezone.now() + timedelta(days=200)
        RegistrationWindow.objects.create(year=self.year, closes_at=closes)
        self.assertEqual(self.hold().expires_at, closes)

    def test_a_held_code_lasts_4_months_at_least(self):
        # As a registered group's is: even when registration closes sooner.
        RegistrationWindow.objects.create(year=self.year, closes_at=timezone.now() + timedelta(days=30))
        held = self.hold()
        self.assertEqual(held.expires_at, held.created_at + timedelta(days=122))

    def test_with_no_closing_date_a_held_code_lasts_the_year(self):
        held = self.hold()
        self.assertEqual(held.expires_at, max(
            datetime(self.year + 1, 1, 1, tzinfo=dt_timezone.utc), held.created_at + timedelta(days=122),
        ))

    def test_a_held_code_moves_with_the_closing_date(self):
        RegistrationWindow.objects.create(year=self.year, closes_at=timezone.now() + timedelta(days=200))
        held = self.hold()
        admin = User.objects.create_user(email="staff@example.com", password="pw-123456789", is_staff=True)
        client = APIClient()
        client.force_login(admin)
        later = timezone.now() + timedelta(days=300)
        response = client.post(
            "/api/v1/registration-management/", {"action": "window", "closes_at": later.isoformat()}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        held.refresh_from_db()
        self.assertEqual(held.expires_at, later)
        # Brought nearer than 4 months from when it was held: those 4 months.
        sooner = timezone.now() + timedelta(days=10)
        response = client.post(
            "/api/v1/registration-management/", {"action": "window", "closes_at": sooner.isoformat()}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        held.refresh_from_db()
        self.assertEqual(held.expires_at, held.created_at + timedelta(days=122))


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
        students = GroupMembership.objects.filter(group=group, membership_role="student")
        self.assertEqual(students.count(), 3)
        self.assertTrue(
            GroupMembership.objects.filter(group=group, user__email="learner50@students.example.test").exists()
        )
        self.assertEqual(Groups.objects.count(), 1)

    def test_joining_inherits_the_groups_recorded_nomination(self):
        code = self.registered_group()
        body = self.joiner(code)
        del body["payload"]["supervisor"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        from apps.users.models import RegistrationSubmission
        original, joined = RegistrationSubmission.objects.order_by("created_at", "pk")
        self.assertEqual(joined.supervisor_details, original.supervisor_details)

    def test_joining_uses_the_groups_assigned_supervisor(self):
        code = self.registered_group()
        group = Groups.objects.get(code=code)
        GroupMembership.objects.create(
            group=group, user=self.supervisor,
            membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
        )
        body = self.joiner(code)
        del body["payload"]["supervisor"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        from apps.users.models import StudentProfile
        self.assertEqual(StudentProfile.objects.get(user__email="learner50@students.example.test").supervisor, self.profile)

    def test_joining_a_legacy_group_without_a_supervisor_saves_nothing(self):
        group = Groups.create_with_code()
        body = self.joiner(group.code)
        del body["payload"]["supervisor"]
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("group.joinCode", response.data["fields"])
        self.assertFalse(User.objects.filter(email="learner50@students.example.test").exists())

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
        self.assertEqual(GroupMembership.objects.filter(group=group, membership_role="student").count(), 1)

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

    def test_no_group_needs_shared_interests(self):
        # A student's group, and a supervisor's from Register one student with
        # students added, whose students chose none.
        for offset, journey in enumerate(("student_team", "supervisor_group")):
            with self.subTest(journey):
                body = batch(journey, offset=offset * 10)
                body["payload"]["group"] = {}
                response = self.post_batch(body)
                self.assertEqual(response.status_code, 201, response.data)


class StudentGroupPlacedTests(MultiStudentSetup, TestCase):
    """A student group goes onto the Groups board by itself once two of its
    students have registered; one on its own waits in the Waiting Area."""

    def test_two_registering_together_go_onto_the_board(self):
        response = self.post_batch(batch("student_team"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(Groups.objects.get(code=response.data["group_code"]).placed_at)

    def test_one_on_their_own_waits_until_a_teammate_joins(self):
        response = self.post_batch(batch("student_team", 1))
        self.assertEqual(response.status_code, 201, response.data)
        group = Groups.objects.get(code=response.data["group_code"])
        self.assertIsNone(group.placed_at)

        body = batch("student_team", 1, offset=20)
        body["payload"]["group"] = {"joinCode": group.code}
        self.assertEqual(self.post_batch(body).status_code, 201)
        group.refresh_from_db()
        self.assertIsNotNone(group.placed_at)

    def test_a_supervisors_group_still_waits_for_create_all_groups(self):
        self.assertEqual(self.post_batch(batch("supervisor_group", offset=10)).status_code, 201)
        self.assertIsNone(Groups.objects.get(formed_by=Groups.FormedBy.SUPERVISOR).placed_at)


class FormedByTests(MultiStudentSetup, TestCase):
    """Who formed each group: its members, a supervisor or an admin, and the person."""

    def test_its_members_or_a_supervisor_by_registering(self):
        body = batch("student_team")
        response = self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        group = Groups.objects.get(code=response.data["group_code"])
        self.assertEqual(group.formed_by, Groups.FormedBy.MEMBERS)
        self.assertEqual(group.created_by.email, body["payload"]["students"][0]["email"])

        response = self.post_batch(batch("supervisor_group", offset=10))
        self.assertEqual(response.status_code, 201, response.data)
        group = Groups.objects.get(code=None)
        self.assertEqual(group.formed_by, Groups.FormedBy.SUPERVISOR)
        self.assertEqual(group.created_by, self.supervisor)

    def test_my_groups_knows_which_formed_while_registering(self):
        from apps.users.supervisor_group_views import _registered_by

        self.post_batch(batch("student_team"))
        self.post_batch(batch("supervisor_group", offset=10))
        made_later = Groups.objects.create(group_name="Made on My Groups")
        made_later.mark_formed(Groups.FormedBy.SUPERVISOR, self.supervisor)
        self.assertEqual(
            sorted(_registered_by(group) for group in Groups.objects.all()),
            ["", "members", "supervisor"],
        )
        # On the supervisor's own list, for My Groups' Waiting Area.
        listed = self.supervisor_client.get("/api/v1/users/supervised-groups/").json()
        self.assertIn("supervisor", [group["registered_by"] for group in listed])

    def test_create_all_groups_makes_the_waiting_ones_biotech_groups(self):
        url = "/api/v1/users/supervised-groups/place/"
        self.post_batch(batch("supervisor_group", offset=10))
        registered = Groups.objects.get(formed_by=Groups.FormedBy.SUPERVISOR)

        # None formed by students here; a kind that isn't one is refused.
        self.assertEqual(self.supervisor_client.post(url, {"registered_by": "members"}, format="json").json(), [])
        self.assertEqual(self.supervisor_client.post(url, {"registered_by": "admin"}, format="json").status_code, 400)

        response = self.supervisor_client.post(url, {"registered_by": "supervisor"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        # Made a BIOTech group, still known as one the supervisor registered.
        self.assertEqual(
            [(g["id"], g["registered_by"], g["placed"]) for g in response.json()],
            [(registered.id, "supervisor", True)],
        )
        registered.refresh_from_db()
        self.assertIsNotNone(registered.placed_at)
        # Nothing waiting now: nothing more to make.
        self.assertEqual(self.supervisor_client.post(url, {"registered_by": "supervisor"}, format="json").json(), [])

        # A student back in the Waiting Area (out of every group) rejoins it.
        student_id = GroupMembership.objects.filter(group=registered, membership_role="student").first().user_id
        GroupMembership.objects.filter(group=registered, user_id=student_id).update(left_at=timezone.now())
        response = self.supervisor_client.post(url, {"registered_by": "supervisor"}, format="json")
        self.assertEqual([g["id"] for g in response.json()], [registered.id])
        self.assertTrue(
            GroupMembership.objects.filter(group=registered, user_id=student_id, left_at__isnull=True).exists()
        )

    def test_each_student_keeps_their_group_from_registering(self):
        self.post_batch(batch("supervisor_group", offset=10))
        self.post_batch(batch("supervisor_individual", offset=20))
        registered = Groups.objects.get(formed_by=Groups.FormedBy.SUPERVISOR)
        roster = self.supervisor_client.get("/api/v1/users/supervised-students/").json()
        homes = sorted((row["registration_group_id"] or 0) for row in roster)
        # The group's students have it, the student registered alone none.
        self.assertEqual(homes, [0] + [registered.id] * (len(roster) - 1))

        # Moved to another group, they still have it, to go back to.
        other = Groups.objects.create(group_name="Made on My Groups")
        moving = next(row for row in roster if row["registration_group_id"])
        GroupMembership.objects.filter(user_id=moving["id"], left_at__isnull=True).update(left_at=timezone.now())
        GroupMembership.objects.create(group=other, user_id=moving["id"], membership_role="student")
        roster = self.supervisor_client.get("/api/v1/users/supervised-students/").json()
        moved = next(row for row in roster if row["id"] == moving["id"])
        self.assertEqual((moved["group_id"], moved["registration_group_id"]), (other.id, registered.id))

    def test_admins_see_who_formed_each_group(self):
        from apps.admin.services.group import create_group, query_groups

        self.post_batch(batch("student_team"))
        self.post_batch(batch("supervisor_group", offset=10))
        admin = User.objects.create_user(email="admin-groups@example.test", first_name="Ada", last_name="Admin")
        create_group("Made by Ada", created_by=admin)
        formed = sorted(
            (group["formedBy"]["kind"], group["formedBy"]["name"]) for group in query_groups()["data"]["items"]
        )
        self.assertEqual(formed[0], ("admin", "Ada Admin"))
        self.assertEqual(formed[1][0], "members")
        self.assertEqual(formed[2], ("supervisor", "Current Supervisor"))
