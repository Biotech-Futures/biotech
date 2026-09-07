"""Creating a support agent from the admin app.

Asked on 2026-09-04 where support agents come from — grant the role to an
existing account, or add a "support" option to registration for an admin to
approve — the client answered neither of the two offered:

    The admin would create a new account for the support agent, similar to how
    they can currently create a new admin user, but rather assign the support
    role to them

So "support" becomes a fifth value of the role the create-user flow already
takes, and its side effect is a SupportScope row where "admin" produces an
AdminScope row. Granting the role to an existing account stays as it was, on
the Support agents roster page: there are two ways in and one way out.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.admin.services.user import (
    UNEXPECTED_FAILURE,
    create_user,
    fetch_user_by_id,
    update_user,
)
from apps.audit.models import AuditLog
from apps.resources.models import Roles
from apps.tickets.models import SupportScope
from apps.tickets.permissions import is_support
from apps.users.models.admin_scope import AdminScope

User = get_user_model()


class CreateSupportAgentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)

    def create(self, **overrides):
        payload = {
            "email": "agent@example.com",
            "firstName": "Sana",
            "lastName": "Reid",
            "role": "support",
        }
        payload.update(overrides)
        return create_user(payload, initiated_by=self.admin)

    def test_it_creates_the_account_and_grants_queue_access(self):
        result = self.create()
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="agent@example.com")
        self.assertTrue(SupportScope.objects.filter(user=user).exists())
        self.assertTrue(is_support(user))

    def test_the_new_agent_is_not_an_administrator(self):
        """The whole reason the role exists. The client's own note on p47 is
        "all admins have support access, but not all support are admins", and
        an agent who arrived as an admin would make the distinction
        meaningless."""
        self.create()
        user = User.objects.get(email="agent@example.com")
        self.assertFalse(AdminScope.objects.filter(user=user).exists())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_no_country_is_required(self):
        """Created "similar to how they can currently create a new admin
        user", and that form asks for a name, an email and a role. Nothing
        reads an agent's country: Ticket.region snapshots the *requester's*."""
        result = self.create()
        self.assertIsNotNone(result["data"], result["msg"])

    def test_creating_a_mentor_still_requires_a_country(self):
        """The exemption is scoped to the two roles that have it, and adding
        support to that list must not have loosened it for anybody else."""
        result = self.create(role="mentor", email="mentor@example.com")
        self.assertIsNone(result["data"])
        self.assertIn("Country", result["msg"])

    def test_the_grant_is_recorded_in_the_audit_log(self):
        """The roster page writes one of these. Without it here, half the ways
        of handing out queue access would be recorded and half would not."""
        self.create()
        user = User.objects.get(email="agent@example.com")
        row = AuditLog.objects.get(
            entity_type="support_scope", entity_id=user.pk, action="create"
        )
        self.assertEqual(row.actor_user_id, self.admin.pk)

    def test_a_duplicate_email_is_refused_and_leaves_nothing_behind(self):
        self.create()
        before = SupportScope.objects.count()
        result = self.create()
        self.assertIsNone(result["data"])
        self.assertEqual(User.objects.filter(email="agent@example.com").count(), 1)
        self.assertEqual(SupportScope.objects.count(), before)

    def test_creating_an_admin_still_grants_admin_and_not_support(self):
        self.create(role="admin", email="admin2@example.com")
        user = User.objects.get(email="admin2@example.com")
        self.assertTrue(AdminScope.objects.filter(user=user).exists())
        self.assertFalse(SupportScope.objects.filter(user=user).exists())


class TheGrantAndItsAuditRowLandTogetherTests(TestCase):
    """The twin of RosterAuditAtomicityTests in tests/apps/tickets/test_api_admin.

    Three paths hand out queue access. The roster page and the role change
    each wrote the grant and the row saying who made it inside one
    transaction; this one wrote the audit row outside every try and every
    transaction. A failure there left the account made, the access live, no
    record of who gave it, a 500 on the admin's screen, and no way to finish
    the job from the interface, because the retry met "Email already exists".

    An unexplained grant on a platform whose users are minors is the worst
    kind, so the two go in together or neither does.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)

    def create(self, **overrides):
        payload = {
            "email": "agent@example.com",
            "firstName": "Sana",
            "lastName": "Reid",
            "role": "support",
        }
        payload.update(overrides)
        return create_user(payload, initiated_by=self.admin)

    def create_with_a_broken_audit_store(self):
        from unittest.mock import patch

        with patch(
            "apps.admin.services.user.log_audit_event",
            side_effect=RuntimeError("audit store down"),
        ):
            return self.create()

    def test_a_failed_audit_write_takes_the_queue_access_with_it(self):
        result = self.create_with_a_broken_audit_store()

        self.assertIsNone(result["data"])
        self.assertEqual(result["msg"], UNEXPECTED_FAILURE)
        self.assertFalse(
            SupportScope.objects.exists(),
            "queue access was granted with no audit row to say who did it",
        )

    def test_it_does_not_leave_half_an_account_behind_either(self):
        """rollback_created_user is the same cleanup the AdminScope branch
        next door already ran. It only ever ran here because the audit write
        moved inside the try."""
        self.create_with_a_broken_audit_store()

        self.assertFalse(User.objects.filter(email="agent@example.com").exists())
        self.assertFalse(
            AuditLog.objects.filter(entity_type="support_scope").exists()
        )

    def test_the_grant_itself_is_rolled_back_and_not_just_cleaned_up_after(self):
        """Isolates the write from the cleanup that follows it.

        rollback_created_user deletes the half-made account, and SupportScope
        cascades from the user, so the cleanup alone would hide whether the
        grant and its audit row were ever one write. With the cleanup stubbed
        out, nothing is left to hide behind.
        """
        from unittest.mock import patch

        with patch("apps.admin.services.user.rollback_created_user"):
            with patch(
                "apps.admin.services.user.log_audit_event",
                side_effect=RuntimeError("audit store down"),
            ):
                self.create()

        self.assertFalse(
            SupportScope.objects.exists(),
            "the grant survived a failed audit write in the same transaction",
        )

    def test_the_admin_can_simply_try_again(self):
        """The part an admin actually feels. A half-made account answers the
        retry with "Email already exists", and there is no screen in the app
        that finishes the job."""
        self.create_with_a_broken_audit_store()

        result = self.create()

        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="agent@example.com")
        self.assertTrue(SupportScope.objects.filter(user=user).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                entity_type="support_scope", entity_id=user.pk, action="create"
            ).exists()
        )


class SavingASupportAccountTests(TestCase):
    """The other half of the geography exemption.

    Adding "support" to the create path's exempt list and not to the update
    path's left the client's own route half-broken in a way no create test
    could see: an admin could make a support agent and then never save one
    again. adminweb sends `countryId: null` for every role without geography,
    and the update path answered "Country cannot be cleared".

    Both paths now read one list, `ROLES_WITHOUT_GEOGRAPHY`, because two
    copies of the rule is what let them drift in the first place.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)

    def make_support_agent(self):
        result = create_user({
            "email": "agent@example.com",
            "firstName": "Sana",
            "lastName": "Reid",
            "role": "support",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        return User.objects.get(email="agent@example.com")

    def test_a_support_account_can_be_saved_again_without_a_country(self):
        user = self.make_support_agent()
        result = update_user(user.pk, {
            "firstName": "Sana",
            "lastName": "Reid-Okafor",
            "role": "support",
            "countryId": None,
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user.refresh_from_db()
        self.assertEqual(user.last_name, "Reid-Okafor")

    def test_an_existing_account_can_be_converted_to_support(self):
        """The client's route in the other direction. It has to work, or the
        Support agents page's own advice — that an admin can hand queue access
        to somebody who already has an account — is only half true."""
        create_user({
            "email": "helper@example.com",
            "firstName": "Grace",
            "lastName": "Okafor",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)
        user = User.objects.get(email="helper@example.com")

        result = update_user(user.pk, {
            "firstName": "Grace",
            "lastName": "Okafor",
            "role": "support",
            "countryId": None,
        }, initiated_by=self.admin)

        self.assertIsNotNone(result["data"], result["msg"])
        self.assertTrue(SupportScope.objects.filter(user=user).exists())

    def test_an_admin_can_still_be_saved_without_a_country(self):
        """The exemption that was already there must survive the change."""
        create_user({
            "email": "boss@example.com",
            "firstName": "Dana",
            "lastName": "Two",
            "role": "admin",
        }, initiated_by=self.admin)
        user = User.objects.get(email="boss@example.com")
        result = update_user(user.pk, {
            "firstName": "Dana",
            "lastName": "Three",
            "role": "admin",
            "countryId": None,
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])

    def test_a_student_still_cannot_have_their_country_cleared(self):
        """The exemption is scoped to two roles, and widening it for support
        must not have widened it for everybody."""
        made = create_user({
            "email": "kid@example.com",
            "firstName": "Ava",
            "lastName": "Nguyen",
            "role": "student",
            "country": "Australia",
            "schoolName": "Sydney Girls High",
            "yearLevel": 11,
            "supervisorEmail": "grace@example.com",
            "supervisorFirstName": "Grace",
            "supervisorLastName": "Okafor",
            "interests": ["Biology"],
        }, initiated_by=self.admin)
        self.assertIsNotNone(made["data"], made["msg"])
        user = User.objects.get(email="kid@example.com")

        result = update_user(user.pk, {
            "firstName": "Ava",
            "lastName": "Nguyen",
            "role": "student",
            "countryId": None,
        }, initiated_by=self.admin)

        self.assertIsNone(result["data"])
        self.assertIn("Country cannot be cleared", result["msg"])

    def test_the_two_paths_read_the_same_list(self):
        """Pinned directly, because the bug was two copies drifting apart and
        a behavioural test can only ever cover the roles somebody thought to
        write a case for."""
        from apps.admin.services import user as user_service

        self.assertEqual(
            set(user_service.ROLES_WITHOUT_GEOGRAPHY), {"admin", "support"}
        )


class WhatAnAdminIsToldWhenSomethingFailsTests(TestCase):
    """The admin app now shows the server's own `msg` on a failed save.

    That was the right fix — an admin who could not save a support agent was
    being told "Unable to update the user right now" while the server had
    already said "Country cannot be cleared". But it changed what these
    strings are: they went from something nothing displayed to something a
    person reads, and five of them were built by interpolating str(exc).

    So: deliberate refusals stay verbatim, because they were written for the
    reader. The "something blew up" cases say one stable sentence and the
    exception goes to the log.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)

    def test_a_deliberate_refusal_still_reaches_the_admin_verbatim(self):
        create_user({
            "email": "taken@example.com", "firstName": "A", "lastName": "B",
            "role": "support",
        }, initiated_by=self.admin)
        again = create_user({
            "email": "taken@example.com", "firstName": "C", "lastName": "D",
            "role": "support",
        }, initiated_by=self.admin)
        self.assertIsNone(again["data"])
        self.assertIn("already exists", again["msg"].lower())

    def test_an_unexpected_failure_does_not_show_the_exception(self):
        """Python exception text in a toast is table names, column names and
        whatever psycopg happened to say."""
        from unittest.mock import patch

        with patch(
            "apps.admin.services.user.resolve_role_id",
            side_effect=RuntimeError("relation \"resources_roles\" does not exist"),
        ):
            result = create_user({
                "email": "boom@example.com", "firstName": "A", "lastName": "B",
                "role": "support",
            }, initiated_by=self.admin)

        self.assertIsNone(result["data"])
        self.assertEqual(result["msg"], UNEXPECTED_FAILURE)
        self.assertNotIn("relation", result["msg"])
        self.assertNotIn("resources_roles", result["msg"])

    def test_the_exception_is_logged_rather_than_thrown_away(self):
        """Hiding it from the admin must not hide it from us."""
        from unittest.mock import patch

        with patch(
            "apps.admin.services.user.resolve_role_id",
            side_effect=RuntimeError("some internal detail"),
        ):
            with self.assertLogs("apps.admin.services.user", level="ERROR") as logs:
                create_user({
                    "email": "boom2@example.com", "firstName": "A", "lastName": "B",
                    "role": "support",
                }, initiated_by=self.admin)

        self.assertTrue(
            any("some internal detail" in line for line in logs.output),
            "the exception has to reach the log if it is not reaching the admin",
        )

    def test_an_unexpected_failure_on_update_says_nothing_was_changed(self):
        """An admin who sees an error needs to know whether to retry. "Nothing
        was changed" is the difference between retrying and double-creating."""
        self.assertIn("nothing was changed", UNEXPECTED_FAILURE.lower())


class SupportAccessFollowsTheRoleChangeTests(TestCase):
    """The landmine on both sides of the SupportScope sync in update_user.

    This function runs on every successful update, not only when the role
    changed; `next_role` falls back to the current role when the caller sends
    none; and adminweb sends `role` on every save. So neither half may key off
    the save alone:

    * Revoking on every save would strip queue access from somebody the roster
      page granted it to, the next time anyone corrected their surname.
    * Granting on every save undid a deliberate revocation — the roster page
      removes the row without touching the role, so the next unrelated save
      put it straight back, with no audit row to show for it.

    What separates them is whether the role actually moved. Access follows a
    move into or out of the "support" role and nothing else; for accounts whose
    role is something else, the roster page remains both the way in and the way
    out.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)
        self.role_supervisor, _ = Roles.objects.get_or_create(role_name="supervisor")

    def make_helper_with_queue_access(self):
        result = create_user({
            "email": "helper@example.com",
            "firstName": "Priya",
            "lastName": "Patel",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="helper@example.com")
        # Granted the way the roster page grants it.
        SupportScope.objects.create(user=user)
        return user

    def test_editing_an_unrelated_field_does_not_strip_queue_access(self):
        """The exact failure: a supervisor who helps with support loses the queue
        the next time anybody corrects the spelling of their surname."""
        user = self.make_helper_with_queue_access()

        update_user(user.pk, {
            "firstName": "Priya",
            "lastName": "Patel-Singh",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)

        self.assertTrue(SupportScope.objects.filter(user=user).exists())

    def test_changing_the_role_of_someone_the_roster_let_in_keeps_their_access(self):
        """Access granted from the roster page survives a role change.

        Their role never said "support" — the roster page is what let them in,
        so it stays the only thing that can put them out, and it is the only
        screen that first says how many unresolved tickets that would strand.

        The interests key matters: without it update_user returns "At least one
        interest is required for student users" and never reaches the block
        under test, so the assertion below would hold on a request that did
        nothing. Hence the msg assertion.
        """
        user = self.make_helper_with_queue_access()

        result = update_user(user.pk, {
            "firstName": "Priya",
            "lastName": "Patel",
            "role": "student",
            "country": "Australia",
            "schoolName": "Sydney Girls High",
            "yearLevel": 11,
            "interests": ["Genetics"],
        }, initiated_by=self.admin)

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertTrue(SupportScope.objects.filter(user=user).exists())

    def test_setting_the_role_to_support_does_grant_access(self):
        result = create_user({
            "email": "later@example.com",
            "firstName": "Omar",
            "lastName": "Haddad",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="later@example.com")
        self.assertFalse(SupportScope.objects.filter(user=user).exists())

        update_user(user.pk, {
            "firstName": "Omar",
            "lastName": "Haddad",
            "role": "support",
        }, initiated_by=self.admin)

        self.assertTrue(SupportScope.objects.filter(user=user).exists())

    def test_editing_an_admin_still_keeps_the_admin_sync_working(self):
        """The admin block is untouched, and this says so out loud: the two
        are asymmetric on purpose, not because one of them was forgotten."""
        result = create_user({
            "email": "boss@example.com",
            "firstName": "Dana",
            "lastName": "Two",
            "role": "admin",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="boss@example.com")
        self.assertTrue(AdminScope.objects.filter(user=user).exists())

        update_user(user.pk, {
            "firstName": "Dana",
            "lastName": "Two",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)

        self.assertFalse(AdminScope.objects.filter(user=user).exists())


class MovingOutOfTheSupportRoleTakesTheQueueTests(TestCase):
    """The other half of the sync: a role that stops saying "support".

    Nothing covered this before. The People page role dropdown looks like it
    changes what somebody can do — the admin entry beside it really is
    two-way — so an account shown as "Student" kept reading every ticket on
    the platform, requester names and email addresses included.

    Every payload here carries the keys adminweb sends for the target role.
    Without them update_user returns a validation message and never reaches
    the block under test, and an assertion about SupportScope would then hold
    on a request that did nothing.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)

    def make_agent(self, *, role_row_spelled="support"):
        """A support agent, with the roles row spelled as asked.

        `resolve_role_id` matches on `role_name__iexact`, so pre-creating the
        row decides the spelling the rest of the platform then reads back.
        """
        Roles.objects.get_or_create(role_name=role_row_spelled)
        result = create_user({
            "email": "agent@example.com",
            "firstName": "Sam",
            "lastName": "Okafor",
            "role": "support",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="agent@example.com")
        self.assertTrue(SupportScope.objects.filter(user=user).exists())
        return user

    def demote_to_student(self, user):
        return update_user(user.pk, {
            "firstName": "Sam",
            "lastName": "Okafor",
            "role": "student",
            "country": "Australia",
            "schoolName": "Sydney Girls High",
            "yearLevel": 10,
            "interests": ["Genetics"],
        }, initiated_by=self.admin)

    def test_demoting_a_support_agent_takes_their_queue_access_away(self):
        user = self.make_agent()

        result = self.demote_to_student(user)

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertFalse(SupportScope.objects.filter(user=user).exists())
        user.refresh_from_db()
        self.assertFalse(is_support(user))

    def test_the_revocation_says_who_did_it(self):
        """An unexplained change to who can read minors' tickets is the one
        kind this platform must never have."""
        user = self.make_agent()

        self.demote_to_student(user)

        row = AuditLog.objects.get(
            entity_type="support_scope", entity_id=user.pk, action="delete"
        )
        self.assertEqual(row.actor_user_id, self.admin.pk)

    def test_promoting_into_support_says_who_did_it_too(self):
        Roles.objects.get_or_create(role_name="supervisor")
        result = create_user({
            "email": "helper@example.com",
            "firstName": "Omar",
            "lastName": "Haddad",
            "role": "supervisor",
            "country": "Australia",
            "supervisorSchoolName": "Sydney Girls High",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="helper@example.com")

        update_user(user.pk, {
            "firstName": "Omar",
            "lastName": "Haddad",
            "role": "support",
        }, initiated_by=self.admin)

        self.assertTrue(SupportScope.objects.filter(user=user).exists())
        row = AuditLog.objects.get(
            entity_type="support_scope", entity_id=user.pk, action="create"
        )
        self.assertEqual(row.actor_user_id, self.admin.pk)

    def test_a_capitalised_role_row_still_revokes(self):
        """The roles table stores free text and `resolve_role_id` reuses rows
        case-insensitively, so the stored spelling can be "Support" while
        adminweb only ever sends "support". Comparing the raw strings sends
        both branches down the wrong path and the row survives the demotion.
        """
        user = self.make_agent(role_row_spelled="Support")
        self.assertEqual(
            Roles.objects.get(id=user.roleassignmenthistory_set.filter(
                valid_to__isnull=True).first().role_id).role_name,
            "Support",
        )

        result = self.demote_to_student(user)

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertFalse(SupportScope.objects.filter(user=user).exists())

    def test_re_saving_a_support_account_does_not_undo_a_revocation(self):
        """The roster page removes the row and leaves the role alone, so on the
        next save the role still reads "support". Granting on that alone put
        the row straight back — an admin revoking access, someone else fixing
        a surname, and the access is quietly back with no audit row naming
        anybody. The last support_scope event on record stayed "delete".
        """
        user = self.make_agent()
        SupportScope.objects.filter(user=user).delete()  # what the roster page does
        audit_before = AuditLog.objects.filter(entity_type="support_scope").count()

        result = update_user(user.pk, {
            "firstName": "Sam",
            "lastName": "Okafor-Bello",   # the unrelated edit
            "role": "support",
        }, initiated_by=self.admin)

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertFalse(SupportScope.objects.filter(user=user).exists())
        self.assertEqual(
            AuditLog.objects.filter(entity_type="support_scope").count(),
            audit_before,
        )

    def test_the_same_role_spelled_differently_is_not_a_role_change(self):
        """Sending "support" against a stored "Support" must not count as a
        move into the role, or a case mismatch alone would re-grant access the
        roster page had just taken away."""
        user = self.make_agent(role_row_spelled="Support")
        SupportScope.objects.filter(user=user).delete()

        result = update_user(user.pk, {
            "firstName": "Sam",
            "lastName": "Okafor",
            "role": "support",
        }, initiated_by=self.admin)

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertFalse(SupportScope.objects.filter(user=user).exists())

    def test_a_capitalised_admin_role_row_keeps_the_console(self):
        """The admin marker beside it reads the same free text. With "Admin"
        stored, an ordinary save fell into the else branch and deleted the
        AdminScope row, dropping that administrator out of the console.

        The role string has to come back the way adminweb sends it, not the
        way this test would like to type it. `fetch_user_by_id` returns the
        spelling held in `roles`, the editor round-trips that value
        untouched, and `next_role` is taken from the payload — so a hardcoded
        lowercase "admin" here exercises a request the client never makes and
        the assertion holds no matter what the code does. Read it back first.
        """
        Roles.objects.get_or_create(role_name="Admin")
        result = create_user({
            "email": "boss@example.com",
            "firstName": "Dana",
            "lastName": "Two",
            "role": "admin",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        user = User.objects.get(email="boss@example.com")
        self.assertTrue(AdminScope.objects.filter(user=user).exists())

        role_as_the_editor_sees_it = fetch_user_by_id(user.pk)["role"]
        self.assertEqual(role_as_the_editor_sees_it, "Admin")

        update_user(user.pk, {
            "firstName": "Dana",
            "lastName": "Three",   # nothing to do with the role
            "role": role_as_the_editor_sees_it,
        }, initiated_by=self.admin)

        self.assertTrue(AdminScope.objects.filter(user=user).exists())


class ImportingCannotHandOutQueueAccessTests(TestCase):
    """A spreadsheet must not be able to make support agents.

    Both bulk endpoints reach the same service, and only one of them checked
    the role: the JSON endpoint validated through BulkUserRowSerializer and
    refused "support", while the CSV endpoint beside it parsed the rows and
    called the service directly. That one created the accounts, granted queue
    access to every one of them and left the audit rows with no actor, so
    "who put this person on the roster" had no answer.

    The check now lives in the service, where both paths meet, rather than in
    a second copy at the second view — a second copy is what let them differ
    for as long as they did.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)
        self.client.force_login(self.admin)

    def csv_import(self, role):
        return self.client.post(
            "/api/v1/admin/user/bulk-csv/",
            {"csv": ("email,firstName,lastName,role,country\n"
                     f"imported@example.com,Sam,Okafor,{role},Australia\n")},
            content_type="application/json",
        )

    def json_import(self, role):
        return self.client.post(
            "/api/v1/admin/user/bulk/",
            [{"email": "imported@example.com", "firstName": "Sam",
              "lastName": "Okafor", "role": role, "country": "Australia",
              "schoolName": "Sydney Girls High", "yearLevel": 10}],
            content_type="application/json",
        )

    def test_a_csv_cannot_create_a_support_agent(self):
        self.csv_import("support")

        self.assertFalse(User.objects.filter(email="imported@example.com").exists())
        self.assertEqual(SupportScope.objects.count(), 0)

    def test_a_csv_cannot_create_an_administrator_either(self):
        """The role that was never importable, and the reason this is a list
        and not a check for one word."""
        self.csv_import("admin")

        self.assertFalse(User.objects.filter(email="imported@example.com").exists())
        self.assertEqual(AdminScope.objects.filter(user__email="imported@example.com").count(), 0)

    def test_a_csv_cannot_invent_a_role(self):
        """resolve_role_id is a get_or_create, so an unknown role did not fail:
        it added a row to the roles table and carried on. The account came out
        holding a role nothing in the platform knows how to read."""
        before = Roles.objects.count()

        self.csv_import("wizard")

        self.assertFalse(User.objects.filter(email="imported@example.com").exists())
        self.assertEqual(Roles.objects.count(), before)

    def test_the_refusal_says_where_to_go_instead(self):
        """A role that exists but is not importable is a different mistake from
        a typo, and the admin can act on the difference."""
        response = self.csv_import("support")

        # The service reports per-row outcomes in the skipped list; the msg is
        # only the tally. A refusal an admin cannot read is a refusal they will
        # retry.
        skipped = response.json()["data"]["skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertIn("People page", skipped[0]["reason"])

    def test_a_csv_still_creates_a_role_an_import_is_for(self):
        """The guard has to leave the endpoint doing its job.

        Supervisor rather than student only because a student row also needs
        an interest, which a CSV column cannot carry — a separate limit of
        this endpoint, older than this change and not touched by it.
        """
        response = self.client.post(
            "/api/v1/admin/user/bulk-csv/",
            {"csv": ("email,firstName,lastName,role,country\n"
                     "head@example.com,Grace,Okafor,supervisor,Australia\n")},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            User.objects.filter(email="head@example.com").exists(),
            response.json()["data"]["skipped"],
        )

    def test_json_and_csv_refuse_the_same_roles(self):
        """The two endpoints disagreeing is the defect itself, so the agreement
        is what gets asserted rather than either one alone."""
        for role in ("support", "admin", "wizard"):
            with self.subTest(role=role):
                self.json_import(role)
                json_made = User.objects.filter(email="imported@example.com").exists()
                self.csv_import(role)
                csv_made = User.objects.filter(email="imported@example.com").exists()
                self.assertEqual(json_made, csv_made)
                self.assertFalse(csv_made)

    def test_the_service_attributes_a_grant_to_whoever_asked_for_it(self):
        """The audit half, tested where it can still happen.

        No import can grant queue access any more, so this exercises the
        service directly with the role allowed. Without initiated_by the audit
        row said access had been given and not by whom, which on a platform
        whose users are minors is the worst kind of record to keep. The two
        views' half of the same wiring is asserted in test_user_service.py,
        which patches the service and checks what it was called with.
        """
        from apps.admin.services.user import ROLES, add_users_by_role

        add_users_by_role(
            [{"email": "agent@example.com", "firstName": "Sam",
              "lastName": "Okafor", "role": "support"}],
            initiated_by=self.admin,
            allowed_roles=ROLES,
        )

        self.assertTrue(SupportScope.objects.filter(user__email="agent@example.com").exists())
        row = AuditLog.objects.get(entity_type="support_scope", action="create")
        self.assertEqual(row.actor_user_id, self.admin.pk)


class ANewSupportAgentCanGetAPasswordTests(TestCase):
    """First login for a role the admin app had never had before.

    Accounts are created with no usable password for every role, and the admin
    app's "do you have one yet" check asked an endpoint behind IsAdminScoped.
    A support agent is deliberately not an administrator, so that check
    answered 403, the client swallowed it, and nothing ever prompted them. The
    page they could reach by hand posted to the matching admin-scoped endpoint
    and told them to try again — which was never going to work.

    The platform already had the answer: /api/v1/set-password/ is role-
    agnostic, and its own docstring records that the portal hit this same wall
    and was moved onto it. The admin app had not been.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pw",
            first_name="Dana", last_name="Ellis",
        )
        AdminScope.objects.create(user=self.admin)
        self.client.force_login(self.admin)
        result = create_user({
            "email": "agent@example.com",
            "firstName": "Sam",
            "lastName": "Okafor",
            "role": "support",
        }, initiated_by=self.admin)
        self.assertIsNotNone(result["data"], result["msg"])
        self.agent = User.objects.get(email="agent@example.com")

    def test_a_new_agent_starts_with_no_usable_password(self):
        """The premise. If this ever stops being true the rest of this class is
        testing a situation that cannot arise."""
        self.assertFalse(self.agent.has_usable_password())

    def test_their_own_account_tells_them_they_need_one(self):
        """What the admin app reads instead of asking an admin-only endpoint."""
        self.client.force_login(self.agent)

        # No {msg, data} envelope on this one: it answers the serializer
        # directly, and AuthProvider stores exactly this object as
        # context.auth.user. So the key the router reads is the key here.
        body = self.client.get("/api/v1/users/me/").json()

        self.assertTrue(body["must_change_password"])
        self.assertFalse(body["isAdmin"])

    def test_they_can_set_it_through_the_role_agnostic_endpoint(self):
        self.client.force_login(self.agent)

        response = self.client.post(
            "/api/v1/set-password/", {"password": "a-long-enough-one"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.has_usable_password())

    def test_the_admin_only_endpoint_still_refuses_them(self):
        """Not a regression — the reason the client had to stop asking it.

        Loosening that guard would have been the other way to fix this, and it
        would have handed an admin-scoped route to a role that is deliberately
        not an administrator.
        """
        self.client.force_login(self.agent)

        self.assertEqual(
            self.client.get("/api/v1/admin/auth/password-status/").status_code, 403
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/auth/set-password/", {"password": "a-long-enough-one"},
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_once_set_they_are_no_longer_asked(self):
        self.client.force_login(self.agent)
        self.client.post(
            "/api/v1/set-password/", {"password": "a-long-enough-one"},
            content_type="application/json",
        )

        body = self.client.get("/api/v1/users/me/").json()

        self.assertFalse(body["must_change_password"])
