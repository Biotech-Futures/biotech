"""Tests for admin mentor match service."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.admin.services.mentor_match import (
    match_mentor, get_mentors, get_unmatched_groups, get_matched_groups,
    confirm_mentor_assignments, replace_mentor,
    unassign_mentors, recommend_mentors_for_group,
    _idle_mentor_ids,
)
from apps.admin.services.match import recommend_students_for_group
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.users.models import (
    MentorProfile, StudentProfile, User, AreasOfInterest, UserInterest,
)
from apps.users.models.admin_scope import AdminScope
from apps.matching_runtime.models import MatchRun
from apps.chat.models import Messages

STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT
MENTOR_ROLE = GroupMembership.MembershipRoleChoices.MENTOR


class MentorMatchServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")

        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)

        self.mentor = User.objects.create_user(
            email="mentor@example.com", first_name="Mina", last_name="Mentor",
            state=self.state, password="testpass", is_active=True,
        )
        MentorProfile.objects.create(
            user=self.mentor, institution="UNSW", mentor_reason="Testing", max_group_count=3,
        )

        self.group = Groups.objects.create(group_name="Group A")
        self.student = User.objects.create_user(
            email="student@example.com", first_name="Stud", last_name="Ent",
            state=self.state, password="testpass",
        )
        StudentProfile.objects.create(
            user=self.student, pg_first_name="P", pg_last_name="E",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        GroupMembership.objects.create(
            user=self.student, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

    def test_match_mentor_returns_empty_when_no_groups_without_mentor(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = match_mentor(str(self.admin_user.id))
        self.assertEqual(result, [])

    def test_get_unmatched_groups(self):
        result = get_unmatched_groups(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["groupName"], "Group A")

    def test_get_unmatched_groups_empty_when_all_matched(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_unmatched_groups(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_unmatched_groups_skips_groups_with_no_students(self):
        Groups.objects.create(group_name="Empty Group")
        result = get_unmatched_groups(requesting_user=self.admin_user)
        self.assertEqual([g["groupName"] for g in result], ["Group A"])

    def test_match_mentor_skips_groups_with_no_students(self):
        Groups.objects.create(group_name="Empty Group")
        result = match_mentor(str(self.admin_user.id))
        self.assertEqual([r["group"]["groupName"] for r in result], ["Group A"])

    def test_get_unmatched_groups_country_is_none_when_no_student_has_a_state(self):
        stateless = Groups.objects.create(group_name="Stateless Group")
        student = User.objects.create_user(
            email="nostate@example.com", first_name="No", last_name="State",
            state=None, password="testpass",
        )
        StudentProfile.objects.create(
            user=student, pg_first_name="P", pg_last_name="E",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        GroupMembership.objects.create(
            user=student, group=stateless, membership_role=STUDENT_ROLE,
        )

        result = get_unmatched_groups(requesting_user=self.admin_user)
        group = next(g for g in result if g["groupName"] == "Stateless Group")
        self.assertIsNone(group["countryName"])

    def test_get_matched_groups(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_matched_groups(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["groupName"], "Group A")
        self.assertEqual(result[0]["mentor"]["name"], "Mina Mentor")

    def test_get_matched_groups_empty_when_unmatched(self):
        result = get_matched_groups(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_mentors(self):
        result = get_mentors(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "mentor@example.com")

    def test_confirm_mentor_assignments_simple(self):
        result = confirm_mentor_assignments({
            "assignments": [{"groupId": self.group.id, "mentorUserId": self.mentor.id}],
        })
        self.assertEqual(result, {"confirmedCount": 1})
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, user=self.mentor,
                left_at__isnull=True,
            ).exists()
        )

    def test_confirm_mentor_assignments_empty(self):
        result = confirm_mentor_assignments({"assignments": []})
        self.assertEqual(result, {"confirmedCount": 0})

    def test_confirm_mentor_assignments_raises_for_non_mentor(self):
        non_mentor = User.objects.create_user(
            email="non-mentor@example.com", first_name="Non", password="testpass",
        )
        with self.assertRaises(ValidationError):
            confirm_mentor_assignments({
                "assignments": [{"groupId": self.group.id, "mentorUserId": non_mentor.id}],
            })

    def test_replace_mentor(self):
        new_mentor = User.objects.create_user(
            email="new@example.com", first_name="New", last_name="Mentor",
            state=self.state, password="testpass", is_active=True,
        )
        MentorProfile.objects.create(
            user=new_mentor, institution="UAT", mentor_reason="Volunteer", max_group_count=3,
        )
        membership = GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = replace_mentor({
            "membershipId": membership.id,
            "groupId": self.group.id,
            "newMentorUserId": new_mentor.id,
        })
        self.assertEqual(result, {"replaced": 1})
        self.assertTrue(
            GroupMembership.objects.filter(group=self.group, user=new_mentor, left_at__isnull=True).exists()
        )

    def _replacement_setup(self):
        """A group with a sitting mentor and a free mentor to swap in."""
        incoming = User.objects.create_user(
            email="incoming@example.com", first_name="Ivy", last_name="Incoming",
            state=self.state, password="testpass", is_active=True,
        )
        MentorProfile.objects.create(
            user=incoming, institution="UAT", mentor_reason="Volunteer", max_group_count=3,
        )
        membership = GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        return membership, incoming

    def test_replace_mentor_emails_both_sides_by_default(self):
        """MR2: the admin opts out of telling a mentor, never in."""
        membership, incoming = self._replacement_setup()

        with mock.patch("apps.admin.services.mentor_match.send_system_email") as send:
            replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": incoming.id,
            })

        sent = {call.args[0]: call.args[1] for call in send.call_args_list}
        self.assertCountEqual(sent, ["mentor_unassigned", "mentor_assigned"])
        self.assertEqual(sent["mentor_unassigned"], [self.mentor.email])
        self.assertEqual(sent["mentor_assigned"], [incoming.email])

    def test_replace_mentor_skips_the_email_the_admin_unticked(self):
        membership, incoming = self._replacement_setup()

        with mock.patch("apps.admin.services.mentor_match.send_system_email") as send:
            replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": incoming.id,
                "notifyDeparting": False,
            })

        self.assertEqual([call.args[0] for call in send.call_args_list], ["mentor_assigned"])

    def test_re_picking_the_sitting_mentor_emails_nobody(self):
        """Choosing the mentor already on the group is a no-op from their side,
        so telling them they were removed and re-added would be nonsense."""
        membership, _ = self._replacement_setup()

        with mock.patch("apps.admin.services.mentor_match.send_system_email") as send:
            replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": self.mentor.id,
            })

        send.assert_not_called()

    def test_bulk_confirm_skips_groups_whose_mentor_did_not_change(self):
        membership, incoming = self._replacement_setup()
        other_group = Groups.objects.create(group_name="Group Two")
        GroupMembership.objects.create(
            user=self.mentor, group=other_group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        with mock.patch("apps.admin.services.mentor_match.send_system_email") as send:
            confirm_mentor_assignments({
                "assignments": [
                    # unchanged: the sitting mentor re-picked
                    {"groupId": self.group.id, "mentorUserId": self.mentor.id},
                    # a real change
                    {"groupId": other_group.id, "mentorUserId": incoming.id},
                ],
            })

        groups_emailed = {
            call.args[2]["GROUP_NAME"] for call in send.call_args_list
        }
        self.assertNotIn(self.group.group_name, groups_emailed)
        self.assertIn(other_group.group_name, groups_emailed)

    def test_a_failed_notification_does_not_undo_the_replacement(self):
        """The membership change is already confirmed, so a bounced email must
        not roll it back or surface to the admin as a failed action."""
        membership, incoming = self._replacement_setup()

        with mock.patch(
            "apps.admin.services.mentor_match.send_system_email",
            side_effect=Exception("smtp down"),
        ):
            result = replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": incoming.id,
            })

        self.assertEqual(result, {"replaced": 1})
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, user=incoming, left_at__isnull=True,
            ).exists()
        )

    def test_replace_mentor_raises_for_non_mentor(self):
        membership = GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        non_mentor = User.objects.create_user(
            email="non@example.com", first_name="Non", password="testpass",
        )
        with self.assertRaises(ValidationError):
            replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": non_mentor.id,
            })

    def test_unassign_mentors(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = unassign_mentors([self.group.id])
        self.assertEqual(result, {"unassignedCount": 1})
        # The membership should still exist (soft unassign via left_at)
        gm = GroupMembership.objects.get(group=self.group, user=self.mentor)
        self.assertIsNotNone(gm.left_at)

    def test_unassign_mentors_none(self):
        result = unassign_mentors([9999])
        self.assertEqual(result, {"unassignedCount": 0})

    def test_match_mentor_saves_run(self):
        existing_mentor_group = Groups.objects.create(group_name="With Mentor")
        GroupMembership.objects.create(
            user=self.mentor, group=existing_mentor_group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = match_mentor(str(self.admin_user.id))
        self.assertTrue(MatchRun.objects.filter(run_type="mentor-match").exists())


class RecommendReplacementTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.interest = AreasOfInterest.objects.create(interest_desc="Biotech")

        self.group = Groups.objects.create(group_name="Group A")
        member = self._student("member@example.com")
        UserInterest.objects.create(user=member, interest=self.interest)
        GroupMembership.objects.create(
            user=member, group=self.group, membership_role=STUDENT_ROLE
        )
        self.current_mentor = self._mentor("mentor@example.com")
        GroupMembership.objects.create(
            user=self.current_mentor, group=self.group, membership_role=MENTOR_ROLE
        )

    def _student(self, email):
        user = User.objects.create_user(
            email=email, first_name="S", last_name=email[:4],
            state=self.state, password="x",
        )
        StudentProfile.objects.create(
            user=user, pg_first_name="P", pg_last_name="G",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        return user

    def _mentor(self, email):
        user = User.objects.create_user(
            email=email, first_name="M", last_name=email[:4],
            state=self.state, is_active=True, password="x",
        )
        MentorProfile.objects.create(
            user=user, institution="UNSW", mentor_reason="Help", max_group_count=3,
        )
        return user

    def test_recommend_mentors_excludes_current_mentor(self):
        other = self._mentor("other@example.com")
        result = recommend_mentors_for_group(self.group.id)
        ids = [s["mentorUserId"] for s in result["data"]["suggestions"]]
        self.assertIn(other.id, ids)
        self.assertNotIn(self.current_mentor.id, ids)

    def test_recommend_mentors_group_not_found(self):
        self.assertIsNone(recommend_mentors_for_group(999999)["data"])

    def test_recommend_students_refuses_formed_group(self):
        # MA3: the group built in setUp already has members, so automatic
        # matching must not offer to drop a standalone student into it.
        sharer = self._student("cand1@example.com")
        UserInterest.objects.create(user=sharer, interest=self.interest)
        result = recommend_students_for_group(self.group.id)
        self.assertIsNone(result["data"])
        self.assertIn("already has members", result["msg"])

    def test_recommend_students_empty_group_has_nothing_to_suggest(self):
        # An empty group is not off-limits, but there are no members to score a
        # candidate against, so there is nothing to suggest - standalone students
        # are formed into brand new groups instead (MA3).
        empty_group = Groups.objects.create(group_name="Group B")
        sharer = self._student("cand2@example.com")
        UserInterest.objects.create(user=sharer, interest=self.interest)
        result = recommend_students_for_group(empty_group.id)
        self.assertEqual(result["data"]["suggestions"], [])

    def test_recommend_students_group_not_found(self):
        self.assertIsNone(recommend_students_for_group(999999)["data"])


class IdleMentorsAreNotRecommendedTests(TestCase):
    """A mentor who has gone quiet is not offered a group.

    "Quiet" is measured against the admin's own threshold, which arrives with
    the request. Never having messaged only counts once they have been
    registered longer than that - a new mentor has had no chance to post, and
    a mentor with no group has nowhere to.
    """

    def setUp(self):
        self.group = Groups.objects.create(group_name="Needs a mentor")
        self.student = User.objects.create_user(
            email="idle-student@example.com", first_name="Sam", password="pw",
        )
        GroupMembership.objects.create(
            user=self.student, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

    def _mentor(self, email, *, joined_days_ago, last_message_days_ago=None,
                in_a_group=True):
        user = User.objects.create_user(email=email, first_name=email[:4], password="pw")
        User.objects.filter(pk=user.pk).update(
            date_joined=timezone.now() - timedelta(days=joined_days_ago)
        )
        MentorProfile.objects.create(user=user, institution="Uni", mentor_reason="Help")
        if in_a_group:
            # Somewhere they could have posted. Mentoring a different group, so
            # this says nothing about the group under test.
            GroupMembership.objects.create(
                user=user,
                group=Groups.objects.create(group_name=f"Already mentoring {email}"),
                membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            )
        if last_message_days_ago is not None:
            message = Messages.objects.create(
                group=self.group, sender_user=user, message_text="hello",
            )
            Messages.objects.filter(pk=message.pk).update(
                sent_at=timezone.now() - timedelta(days=last_message_days_ago)
            )
        return user

    def _suggested_ids(self, idle_days=30):
        result = recommend_mentors_for_group(self.group.id, idle_days)
        return {item["mentorUserId"] for item in result["data"]["suggestions"]}

    def test_a_mentor_who_spoke_recently_is_recommended(self):
        recent = self._mentor("recent@example.com", joined_days_ago=200, last_message_days_ago=3)

        self.assertIn(recent.id, self._suggested_ids())

    def test_a_mentor_who_has_gone_quiet_is_not(self):
        quiet = self._mentor("quiet@example.com", joined_days_ago=200, last_message_days_ago=90)

        self.assertNotIn(quiet.id, self._suggested_ids())

    def test_a_newly_registered_mentor_is_still_recommended(self):
        # They have not had the time to post yet.
        fresh = self._mentor("fresh@example.com", joined_days_ago=2)

        self.assertIn(fresh.id, self._suggested_ids())

    def test_a_long_registered_mentor_who_never_posted_is_not(self):
        silent = self._mentor("silent@example.com", joined_days_ago=200)

        self.assertNotIn(silent.id, self._suggested_ids())

    def test_a_mentor_with_no_group_is_recommended_however_long_they_are_quiet(self):
        # The deadlock this avoids: they are passed over for never having
        # posted, and cannot post without a group to post in. Silence only
        # counts against a mentor who had somewhere to speak.
        unassigned = self._mentor(
            "unassigned@example.com", joined_days_ago=400, in_a_group=False
        )

        self.assertIn(unassigned.id, self._suggested_ids())

    def test_a_mentor_who_left_their_only_group_is_recommended(self):
        # Same reasoning once the membership ends: there is nowhere to post.
        departed = self._mentor("departed@example.com", joined_days_ago=400)
        GroupMembership.objects.filter(user=departed).update(left_at=timezone.now())

        self.assertIn(departed.id, self._suggested_ids())

    def test_the_admins_own_threshold_decides(self):
        mentor = self._mentor("tuned@example.com", joined_days_ago=200, last_message_days_ago=45)

        # Quiet for 45 days: idle at the default 30, not yet at 60.
        self.assertNotIn(mentor.id, self._suggested_ids(30))
        self.assertIn(mentor.id, self._suggested_ids(60))


class IneligibleMentorsAreRefusedTests(TestCase):
    """The mutations enforce what the screens only filter.

    Both the admin screens and ``recommend_mentors_for_group`` leave out
    deactivated and idle mentors, but that is presentation. A stale frontend or
    a scripted request posts straight to the mutation, so the rule is enforced
    there too - once, in a check both paths share.
    """

    def setUp(self):
        self.group = Groups.objects.create(group_name="Needs a mentor")
        self.other_group = Groups.objects.create(group_name="Also needs one")
        self.student = User.objects.create_user(
            email="elig-student@example.com", first_name="Sam", password="pw",
        )
        GroupMembership.objects.create(
            user=self.student, group=self.group, membership_role=STUDENT_ROLE,
        )

    def _mentor(self, email, *, is_active=True, joined_days_ago=400,
                last_message_days_ago=None, group=None):
        user = User.objects.create_user(
            email=email, first_name=email[:4], password="pw",
        )
        User.objects.filter(pk=user.pk).update(
            date_joined=timezone.now() - timedelta(days=joined_days_ago),
            is_active=is_active,
        )
        MentorProfile.objects.create(
            user=user, institution="Uni", mentor_reason="Help", max_group_count=5,
        )
        if group is not None:
            GroupMembership.objects.create(
                user=user, group=group, membership_role=MENTOR_ROLE,
            )
        if last_message_days_ago is not None:
            message = Messages.objects.create(
                group=group or self.group, sender_user=user, message_text="hi",
            )
            Messages.objects.filter(pk=message.pk).update(
                sent_at=timezone.now() - timedelta(days=last_message_days_ago)
            )
        return user

    def _sitting(self, group):
        """The mentor currently on ``group``, and their membership id."""
        mentor = self._mentor(
            "sitting-%s@example.com" % group.id,
            last_message_days_ago=90,
            group=group,
        )
        membership_id = GroupMembership.objects.get(
            user=mentor, group=group, membership_role=MENTOR_ROLE,
        ).id
        return mentor, membership_id

    # -- single replace -----------------------------------------------------

    def test_replace_refuses_a_deactivated_mentor(self):
        _, membership_id = self._sitting(self.group)
        disabled = self._mentor("disabled@example.com", is_active=False)

        with self.assertRaises(ValidationError) as caught:
            replace_mentor({
                "membershipId": membership_id,
                "groupId": self.group.id,
                "newMentorUserId": disabled.id,
            })

        detail = caught.exception.detail["newMentorUserId"]
        self.assertEqual(detail["ineligible"][0]["reason"], "inactive")
        # The swap did not happen.
        self.assertFalse(
            GroupMembership.objects.filter(
                user=disabled, group=self.group, left_at__isnull=True,
            ).exists()
        )

    def test_replace_refuses_an_idle_mentor(self):
        _, membership_id = self._sitting(self.group)
        quiet = self._mentor(
            "quiet@example.com", last_message_days_ago=90, group=self.other_group,
        )

        with self.assertRaises(ValidationError) as caught:
            replace_mentor({
                "membershipId": membership_id,
                "groupId": self.group.id,
                "newMentorUserId": quiet.id,
            })

        detail = caught.exception.detail["newMentorUserId"]
        self.assertEqual(detail["ineligible"][0]["reason"], "idle")

    def test_replace_honours_the_threshold_sent_with_the_request(self):
        # Quiet for 45 days: idle at the default 30, not at 60. Enforcing a
        # fixed 30 here would reject what the screen just offered.
        _, membership_id = self._sitting(self.group)
        mentor = self._mentor(
            "tuned@example.com", last_message_days_ago=45, group=self.other_group,
        )
        payload = {
            "membershipId": membership_id,
            "groupId": self.group.id,
            "newMentorUserId": mentor.id,
        }

        with self.assertRaises(ValidationError):
            replace_mentor(dict(payload))

        self.assertEqual(replace_mentor({**payload, "idleDays": 60}), {"replaced": 1})

    def test_a_threshold_big_enough_to_disable_the_check_is_clamped(self):
        _, membership_id = self._sitting(self.group)
        quiet = self._mentor(
            "huge@example.com", last_message_days_ago=900, group=self.other_group,
        )

        with self.assertRaises(ValidationError):
            replace_mentor({
                "membershipId": membership_id,
                "groupId": self.group.id,
                "newMentorUserId": quiet.id,
                "idleDays": 10000,
            })

    def test_replace_still_allows_re_picking_the_sitting_mentor(self):
        # A no-op: they are already on the group, so there is nothing to guard
        # against, and refusing would break a harmless request.
        sitting, membership_id = self._sitting(self.group)

        result = replace_mentor({
            "membershipId": membership_id,
            "groupId": self.group.id,
            "newMentorUserId": sitting.id,
        })

        self.assertEqual(result, {"replaced": 1})

    def test_replace_allows_a_mentor_with_no_group(self):
        # Never posted and never could. Refusing them would be the deadlock the
        # idle rule already avoids everywhere else.
        _, membership_id = self._sitting(self.group)
        unassigned = self._mentor("spare@example.com")

        result = replace_mentor({
            "membershipId": membership_id,
            "groupId": self.group.id,
            "newMentorUserId": unassigned.id,
        })

        self.assertEqual(result, {"replaced": 1})

    # -- bulk confirm -------------------------------------------------------

    def test_confirm_refuses_a_deactivated_mentor(self):
        disabled = self._mentor("bulk-disabled@example.com", is_active=False)

        with self.assertRaises(ValidationError) as caught:
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.group.id, "mentorUserId": disabled.id},
                ],
            })

        detail = caught.exception.detail["assignments"]
        self.assertEqual(detail["ineligible"][0]["reason"], "inactive")
        self.assertFalse(
            GroupMembership.objects.filter(
                user=disabled, left_at__isnull=True,
            ).exists()
        )

    def test_confirm_refuses_an_idle_mentor(self):
        quiet = self._mentor(
            "bulk-quiet@example.com",
            last_message_days_ago=90,
            group=self.other_group,
        )

        with self.assertRaises(ValidationError) as caught:
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.group.id, "mentorUserId": quiet.id},
                ],
            })

        self.assertEqual(
            caught.exception.detail["assignments"]["ineligible"][0]["reason"], "idle"
        )

    def test_confirm_checks_a_sitting_mentors_other_arrival(self):
        # Sitting on one group does not excuse arriving at a second. Exempting
        # by mentor id alone would let this through.
        quiet = self._mentor(
            "bulk-both@example.com", last_message_days_ago=90, group=self.other_group,
        )

        with self.assertRaises(ValidationError):
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.other_group.id, "mentorUserId": quiet.id},
                    {"groupId": self.group.id, "mentorUserId": quiet.id},
                ],
            })

    def test_confirm_allows_a_sitting_mentor_re_confirmed_alone(self):
        quiet = self._mentor(
            "bulk-noop@example.com", last_message_days_ago=90, group=self.other_group,
        )

        result = confirm_mentor_assignments({
            "assignments": [
                {"groupId": self.other_group.id, "mentorUserId": quiet.id},
            ],
        })

        self.assertEqual(result, {"confirmedCount": 1})

    # -- the deliberate override ------------------------------------------

    def test_allow_idle_lets_an_admin_assign_a_quiet_mentor_on_purpose(self):
        # The flow that edits one mentor's own group list. Quiet is a reason
        # not to suggest someone, not a reason to stop an admin naming them.
        quiet = self._mentor(
            "named@example.com", last_message_days_ago=90, group=self.other_group,
        )

        result = confirm_mentor_assignments({
            "assignments": [
                {"groupId": self.group.id, "mentorUserId": quiet.id},
            ],
            "allowIdle": True,
        })

        self.assertEqual(result, {"confirmedCount": 1})

    def test_allow_idle_does_not_waive_the_account_check(self):
        # The one rule no path may override: a deactivated account is managed
        # on the Users page, not worked around from here.
        disabled = self._mentor("named-disabled@example.com", is_active=False)

        with self.assertRaises(ValidationError) as caught:
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.group.id, "mentorUserId": disabled.id},
                ],
                "allowIdle": True,
            })

        self.assertEqual(
            caught.exception.detail["assignments"]["ineligible"][0]["reason"],
            "inactive",
        )

    def test_the_suggestion_driven_paths_do_not_set_the_override(self):
        # Guards the split: replace_mentor has no override at all, so a quiet
        # mentor offered by a stale dropdown is still refused.
        _, membership_id = self._sitting(self.group)
        quiet = self._mentor(
            "stale@example.com", last_message_days_ago=90, group=self.other_group,
        )

        with self.assertRaises(ValidationError):
            replace_mentor({
                "membershipId": membership_id,
                "groupId": self.group.id,
                "newMentorUserId": quiet.id,
                "allowIdle": True,
            })


class IdleRuleMatchesTheScreensTests(TestCase):
    """The edges where the matcher and the admin screens must agree.

    Time is frozen, because "exactly at the threshold" is only meaningful
    against a fixed instant: computing it from a second ``now()`` would land a
    few microseconds past the cutoff and test nothing.
    """

    FROZEN = datetime(2026, 10, 27, 12, 0, 0, tzinfo=dt_timezone.utc)

    def setUp(self):
        self.group = Groups.objects.create(group_name="Needs a mentor")
        self.mentor_group = Groups.objects.create(group_name="Already mentoring")
        self.student = User.objects.create_user(
            email="boundary-student@example.com", first_name="Sam", password="pw",
        )
        GroupMembership.objects.create(
            user=self.student, group=self.group, membership_role=STUDENT_ROLE,
        )
        # Registered long ago, so only the message under test decides.
        self.mentor = User.objects.create_user(
            email="boundary-mentor@example.com", first_name="Mo", password="pw",
        )
        User.objects.filter(pk=self.mentor.pk).update(
            date_joined=self.FROZEN - timedelta(days=400)
        )
        MentorProfile.objects.create(
            user=self.mentor, institution="Uni", mentor_reason="Help",
        )
        # Somewhere to have posted, so the no-group exemption is not what is
        # being measured here.
        GroupMembership.objects.create(
            user=self.mentor, group=self.mentor_group, membership_role=MENTOR_ROLE,
        )

    def _post(self, *, days_ago=0, seconds_later=0, deleted=False):
        message = Messages.objects.create(
            group=self.mentor_group, sender_user=self.mentor, message_text="hi",
        )
        Messages.objects.filter(pk=message.pk).update(
            sent_at=(
                self.FROZEN
                - timedelta(days=days_ago)
                + timedelta(seconds=seconds_later)
            ),
            deleted_at=self.FROZEN if deleted else None,
        )

    def _is_idle(self, idle_days=30):
        with mock.patch("django.utils.timezone.now", return_value=self.FROZEN):
            return self.mentor.id in _idle_mentor_ids([self.mentor.id], idle_days)

    # -- deleted messages still count --------------------------------------

    def test_a_recent_message_counts_as_activity(self):
        self._post(days_ago=3)

        self.assertFalse(self._is_idle())

    def test_a_recent_message_still_counts_once_deleted(self):
        # Deleting a message must not be a route to being marked idle: the
        # mentor turned up, which is what the rule measures.
        self._post(days_ago=3, deleted=True)

        self.assertFalse(self._is_idle())

    def test_an_old_deleted_message_does_not_rescue_a_quiet_mentor(self):
        # Counting deleted messages is not the same as ignoring the threshold.
        self._post(days_ago=90, deleted=True)

        self.assertTrue(self._is_idle())

    def test_both_payloads_report_a_deleted_message_as_the_last_one(self):
        # The screens badge from lastMessageAt, so leaving deleted messages out
        # of these would contradict the rule above: the matcher would hold a
        # mentor active while the row beside that score called them idle.
        self._post(days_ago=3, deleted=True)
        expected = self.FROZEN - timedelta(days=3)

        with mock.patch("django.utils.timezone.now", return_value=self.FROZEN):
            roster = {m["mentorId"]: m for m in get_mentors()}
            matched = {
                group["mentor"]["mentorId"]: group["mentor"]
                for group in get_matched_groups()
            }

        self.assertEqual(roster[self.mentor.id]["lastMessageAt"], expected)
        self.assertEqual(matched[self.mentor.id]["lastMessageAt"], expected.isoformat())

    # -- the threshold means what the admin set -----------------------------

    def test_silence_of_exactly_the_threshold_is_idle(self):
        # "Idle after 30 days" has to include a mentor quiet for exactly 30.
        self._post(days_ago=30)

        self.assertTrue(self._is_idle(30))

    def test_silence_a_moment_short_of_the_threshold_is_not(self):
        # The other side of the same edge, so it is pinned from both
        # directions rather than only the strict one.
        self._post(days_ago=30, seconds_later=1)

        self.assertFalse(self._is_idle(30))

    def test_the_edge_follows_the_threshold_the_admin_set(self):
        # Quiet for 40 days: idle at 40, and still idle at 39, but not at 41.
        self._post(days_ago=40)

        self.assertTrue(self._is_idle(40))
        self.assertTrue(self._is_idle(39))
        self.assertFalse(self._is_idle(41))

    def test_a_grace_of_exactly_the_threshold_has_run_out(self):
        # The join-date grace ends at the same edge, read the same way.
        User.objects.filter(pk=self.mentor.pk).update(
            date_joined=self.FROZEN - timedelta(days=30)
        )

        self.assertTrue(self._is_idle(30))

    def test_a_grace_a_moment_short_of_the_threshold_still_holds(self):
        User.objects.filter(pk=self.mentor.pk).update(
            date_joined=self.FROZEN - timedelta(days=30) + timedelta(seconds=1)
        )

        self.assertFalse(self._is_idle(30))
