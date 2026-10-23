import copy
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.common.storage import get_profile_image_storage, reset_managed_storage_caches
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    AdminScope, KnownUniversity, RegistrationInvitation, RegistrationSubmission,
    RegistrationWindow, StudentProfile, StudentSupervisor, SupervisorProfile, User,
)
from apps.users.registration_intake import invitation_token, save_student, token_hash
from apps.users.serializers import UserRegisterBodySerializer, UserSerializer


INTAKE = "/api/v1/registration"
MANAGEMENT = "/api/v1/registration-management/"


def request_body():
    return {
        "journey": "student_individual",
        "policiesAgreed": True,
        "payload": {
            "students": [{
                "firstName": "Jordan", "lastName": "Lee", "email": "jordan.lee@example.com",
                "school": "Example High", "yearLevel": "10", "country": "Australia", "state": "NSW",
                "interests": ["Biotechnology", "Engineering"], "pronouns": "they/them",
                "pronounsOther": "", "profilePhoto": None, "guardianDeferred": False,
                "guardian": {
                    "firstName": "Taylor", "lastName": "Lee", "email": "guardian@example.com",
                    "phone": "+61 400 000 000", "relationship": "Parent", "relationshipOther": "",
                },
                "overrides": {},
            }],
            "supervisor": {
                "firstName": "Sam", "lastName": "Teacher", "email": "teacher@example.com",
            },
            "source": {"method": "student_individual"},
        },
    }


class RegistrationSetup:
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="staff@example.com", password="staff-test-password", is_staff=True,
            first_name="Staff", last_name="Member",
        )
        self.staff_client = APIClient()
        self.staff_client.force_login(self.staff)
        for name in ("student", "supervisor", "admin"):
            Roles.objects.get_or_create(role_name=name)
        self.window = RegistrationWindow.objects.create(year=timezone.now().year)
        self.body = request_body()

    def mint(self, expires=None):
        response = self.staff_client.post(MANAGEMENT, {
            "action": "invite", "expires_at": (expires or timezone.now() + timedelta(hours=47)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def submit(self, *, body=None, token="", key=None, client=None, url=INTAKE):
        return (client or self.client).post(
            url, body if body is not None else self.body, format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()), HTTP_X_REGISTRATION_INVITATION=token,
        )

    def close_window(self):
        self.window.closes_at = timezone.now() - timedelta(seconds=1)
        self.window.save(update_fields=["closes_at"])

    def assert_not_consumed(self, invite):
        item = RegistrationInvitation.objects.get(pk=invite["id"])
        self.assertIsNone(item.used_at)
        self.assertEqual(RegistrationSubmission.objects.count(), 0)
        self.assertEqual(StudentProfile.objects.count(), 0)


class ManagementTests(RegistrationSetup, TestCase):
    def test_anonymous_cannot_mint_list_or_revoke(self):
        for method, data in (("get", None), ("post", {"action": "invite"}), ("post", {"action": "revoke_invite", "id": 1})):
            response = getattr(self.client, method)(MANAGEMENT, data, format="json")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(RegistrationInvitation.objects.count(), 0)

    def test_non_staff_and_supervisor_cannot_manage(self):
        for name in ("student", "supervisor"):
            user = User.objects.create_user(
                email=f"{name}@example.com", password="test-password", first_name=name, last_name="User",
            )
            RoleAssignmentHistory.objects.create(
                user=user, role=Roles.objects.get(role_name=name), valid_from=timezone.now(),
            )
            client = APIClient()
            client.force_login(user)
            for method, data in (("get", None), ("post", {"action": "invite"}), ("post", {"action": "revoke_invite", "id": 1})):
                self.assertEqual(getattr(client, method)(MANAGEMENT, data, format="json").status_code, 403)

    def test_scoped_admin_without_staff_flag_can_manage(self):
        self.staff.is_staff = False
        self.staff.save(update_fields=["is_staff"])
        AdminScope.objects.create(user=self.staff)
        self.assertEqual(self.staff_client.get(MANAGEMENT).status_code, 200)
        self.mint()

    def test_suspended_staff_cannot_manage(self):
        self.staff.suspend()
        self.assertEqual(self.staff_client.get(MANAGEMENT).status_code, 403)

    def test_authenticated_management_requires_csrf_for_all_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        for data in (
            {"action": "invite", "expires_at": (timezone.now() + timedelta(days=1)).isoformat()},
            {"action": "window", "closes_at": timezone.now().isoformat()},
            {"action": "revoke_invite", "id": 1},
        ):
            self.assertEqual(client.post(MANAGEMENT, data, format="json").status_code, 403)
        csrf = client.get("/api/v1/services/csrf/").json()["csrfToken"]
        minted = client.post(MANAGEMENT, {
            "action": "invite", "expires_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(minted.status_code, 201)
        revoked = client.post(MANAGEMENT, {"action": "revoke_invite", "id": minted.data["id"]},
                              format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(revoked.status_code, 200)

    def test_presets_and_custom_expiry_keep_exact_precision(self):
        now = timezone.now()
        for duration in (timedelta(hours=24), timedelta(hours=47), timedelta(days=7),
                         timedelta(days=14), timedelta(days=3, seconds=17, microseconds=123456)):
            with self.subTest(duration=duration):
                expected = now + duration
                result = self.mint(expected)
                row = RegistrationInvitation.objects.get(pk=result["id"])
                self.assertEqual(row.expires_at, expected)
                self.assertEqual(result["expires_at"], expected)

    def test_only_future_expiry_and_known_actions_are_accepted(self):
        for value in (None, "", "nonsense", timezone.now().isoformat(),
                      (timezone.now() - timedelta(days=1)).isoformat()):
            response = self.staff_client.post(MANAGEMENT, {"action": "invite", "expires_at": value}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("expires_at", response.data["fields"])
        for action in ("grant", "unknown", {}, []):
            response = self.staff_client.post(MANAGEMENT, {"action": action}, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(RegistrationInvitation.objects.count(), 0)

    def test_list_recovers_same_signed_link_without_plaintext_token_storage(self):
        created = self.mint()
        listed = self.staff_client.get(MANAGEMENT).data["invitations"][0]
        self.assertEqual(created["token"], listed["token"])
        self.assertEqual(created["url"], listed["url"])
        self.assertIn("/#/register?invite=", listed["url"])
        self.assertEqual(listed["status"], "active")
        row = RegistrationInvitation.objects.get(pk=created["id"])
        self.assertEqual(row.token_hash, token_hash(created["token"]))
        self.assertNotIn(created["token"], str(row.__dict__))
        self.assertEqual(row.created_by, self.staff)

    def test_rotation_explicitly_marks_unrecoverable_links(self):
        self.mint()
        with override_settings(SECRET_KEY="different-signing-key"):
            # Authentication also uses SECRET_KEY; force-auth only for this
            # key-rotation serialization assertion.
            self.staff_client.force_authenticate(self.staff)
            listed = self.staff_client.get(MANAGEMENT).data["invitations"][0]
        self.assertEqual(listed["status"], "signing_key_changed")
        self.assertIsNone(listed["token"])
        self.assertIsNone(listed["url"])

    def test_revoke_is_idempotent_and_token_becomes_unusable(self):
        invite = self.mint()
        first = self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": invite["id"]}, format="json")
        second = self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": invite["id"]}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.data["revoked_at"], first.data["revoked_at"])
        self.assertEqual(second.data["status"], "revoked")
        self.assertEqual(self.submit(token=invite["token"]).status_code, 400)
        self.assert_not_consumed(invite)

    def test_listing_distinguishes_used_and_exactly_expired_links(self):
        now = timezone.now()
        used = self.mint(now + timedelta(hours=1))
        expired = self.mint(now + timedelta(hours=1))
        self.assertEqual(self.submit(token=used["token"]).status_code, 201)
        with patch("apps.users.registration_intake.timezone.now", return_value=now + timedelta(hours=1)):
            items = {item["id"]: item for item in self.staff_client.get(MANAGEMENT).data["invitations"]}
        self.assertEqual(items[used["id"]]["status"], "used")
        self.assertEqual(items[expired["id"]]["status"], "expired")
        # Who registered with each: the used link's student, none yet for the other.
        registered = RegistrationSubmission.objects.get(invitation_id=used["id"]).student.email
        self.assertEqual((items[used["id"]]["email"], items[expired["id"]]["email"]), (registered, ""))

    def test_invalid_or_wrong_year_revoke_ids_are_rejected(self):
        for value in (None, "", 0, [], "abc"):
            self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": value},
                                                   format="json").status_code, 400)
        self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": 99999},
                                               format="json").status_code, 404)
        other = RegistrationWindow.objects.create(year=self.window.year - 1)
        item = RegistrationInvitation(window=other, created_by=self.staff, expires_at=timezone.now() + timedelta(days=1))
        item.token_hash = token_hash(invitation_token(item))
        item.save()
        self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": item.pk},
                                               format="json").status_code, 404)

    def test_window_controls_are_separate_and_validate_order(self):
        now = timezone.now()
        response = self.staff_client.post(MANAGEMENT, {
            "action": "window", "opens_at": now.isoformat(), "closes_at": (now - timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "window", "year": self.window.year + 1},
                                               format="json").status_code, 400)
        self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "window", "challenge_deadline": now.isoformat()},
                                               format="json").status_code, 400)
        response = self.staff_client.post(MANAGEMENT, {
            "action": "window", "opens_at": (now - timedelta(days=1)).isoformat(), "closes_at": now.isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.submit().status_code, 400)

    def test_listing_is_bounded_and_page_is_validated(self):
        for _ in range(101):
            self.mint()
        first = self.staff_client.get(MANAGEMENT).data
        second = self.staff_client.get(MANAGEMENT, {"page": 2}).data
        self.assertEqual(first["count"], 101)
        self.assertEqual(len(first["invitations"]), 100)
        self.assertEqual(len(second["invitations"]), 1)
        self.assertEqual(self.staff_client.get(MANAGEMENT, {"page": 0}).status_code, 400)


class IntakeTests(RegistrationSetup, TestCase):
    def test_open_registration_saves_an_active_student_and_real_receipt(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        # With the token to set their password next (apps.users.registration_password).
        self.assertEqual(
            set(response.data), {"reference_code", "journey", "student_count", "created_at", "passwordToken"},
        )
        self.assertEqual(response.data["student_count"], 1)
        self.assertEqual(response.data["journey"], "student_individual")
        row = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual(row.created_at.isoformat(), response.data["created_at"])
        user = row.student
        profile = StudentProfile.objects.get(user=user)
        # Active straight away: a student is never Pending.
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNotNone(user.activated_at)
        self.assertFalse(profile.has_join_permission)
        self.assertIsNone(profile.joinperm_responseID)
        self.assertEqual(profile.pg_email, "guardian@example.com")
        self.assertEqual(user.pronouns, "they/them")
        self.assertEqual(user.userinterest_set.count(), 2)
        self.assertEqual(row.guardian_phone, "+61 400 000 000")
        self.assertEqual(row.guardian_relationship, "Parent")
        self.assertEqual(row.source, {"method": "student_individual"})
        self.assertEqual(RoleAssignmentHistory.objects.count(), 1)
        self.assertEqual(RoleAssignmentHistory.objects.get().role.role_name, "student")
        self.assertEqual(SupervisorProfile.objects.count(), 0)
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())
        self.assertEqual(row.supervisor_details["email"], "teacher@example.com")

    def test_areas_of_interest_are_optional(self):
        self.body["payload"]["students"][0]["interests"] = []
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        row = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual(row.student.userinterest_set.count(), 0)

    def test_a_guardian_needs_only_their_name_and_email(self):
        guardian = self.body["payload"]["students"][0]["guardian"]
        guardian.update({"phone": "", "relationship": "", "relationshipOther": ""})
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        row = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual(row.guardian_relationship, "")
        self.assertEqual(StudentProfile.objects.get(user=row.student).pg_email, "guardian@example.com")

    def test_existing_supervisor_is_not_renamed_or_given_a_new_role(self):
        sup = User.objects.create_user(email="teacher@example.com", first_name="Original", last_name="Name")
        profile = SupervisorProfile.objects.create(user=sup, school_name="Original School")
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        sup.refresh_from_db()
        self.assertEqual(sup.first_name, "Original")
        self.assertEqual(sup.last_name, "Name")
        self.assertEqual(profile.school_name, "Original School")
        self.assertFalse(RoleAssignmentHistory.objects.filter(user=sup).exists())
        self.assertEqual(StudentProfile.objects.get().supervisor, profile)

    def test_closed_window_requires_valid_single_student_link(self):
        self.close_window()
        self.assertEqual(self.submit().status_code, 400)
        invite = self.mint()
        response = self.submit(token=invite["token"])
        self.assertEqual(response.status_code, 201, response.data)
        row = RegistrationInvitation.objects.get(pk=invite["id"])
        self.assertIsNotNone(row.used_at)
        self.assertEqual(RegistrationSubmission.objects.get().invitation, row)

    def test_missing_window_preserves_unconfigured_legacy_open_default(self):
        self.window.delete()
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(RegistrationWindow.objects.count(), 1)

    def test_exact_window_open_and_close_boundaries(self):
        now = timezone.now()
        self.window.opens_at = now
        self.window.closes_at = now + timedelta(days=1)
        self.window.save()
        for at, expected in ((now - timedelta(microseconds=1), 400),
                             (self.window.closes_at, 400), (now, 201)):
            with patch("apps.users.registration_intake.timezone.now", return_value=at):
                response = self.submit()
            self.assertEqual(response.status_code, expected, response.data)

    def test_expiry_boundary_and_invalid_links_never_consume(self):
        now = timezone.now()
        invite = self.mint(now + timedelta(hours=1))
        for token, at in (
            ("malformed", now), (invite["token"] + "x", now),
            (invite["token"], now + timedelta(hours=1)),
            (invite["token"], now + timedelta(hours=2)),
        ):
            with patch("apps.users.registration_intake.timezone.now", return_value=at):
                self.assertEqual(self.submit(token=token).status_code, 400)
            self.assert_not_consumed(invite)
        with patch("apps.users.registration_intake.timezone.now", return_value=now + timedelta(hours=1) - timedelta(microseconds=1)):
            self.assertEqual(self.submit(token=invite["token"]).status_code, 201)

    def test_wrong_journeys_and_student_counts_are_rejected_without_consumption(self):
        invite = self.mint()
        for journey in ("student_team", "supervisor_individual", "supervisor_group", "supervisor_csv", "mentor"):
            body = copy.deepcopy(self.body)
            body["journey"] = journey
            self.assertEqual(self.submit(body=body, token=invite["token"]).status_code, 400)
            self.assert_not_consumed(invite)
        for students in ([], self.body["payload"]["students"] * 2):
            body = copy.deepcopy(self.body)
            body["payload"]["students"] = students
            self.assertEqual(self.submit(body=body, token=invite["token"]).status_code, 400)
            self.assert_not_consumed(invite)

    def test_wrong_year_or_wrong_token_journey_is_rejected(self):
        invite = self.mint()
        item = RegistrationInvitation.objects.get(pk=invite["id"])
        item.window = RegistrationWindow.objects.create(year=self.window.year - 1)
        item.token_hash = token_hash(invitation_token(item))
        item.save()
        self.assertEqual(self.submit(token=invitation_token(item)).status_code, 400)
        item.window = self.window
        item.journey = "supervisor_individual"
        item.token_hash = token_hash(invitation_token(item))
        item.save()
        self.assertEqual(self.submit(token=invitation_token(item)).status_code, 400)
        self.assert_not_consumed(invite)

    def test_reuse_rejected_but_unchanged_retry_returns_same_receipt_after_expiry(self):
        invite = self.mint()
        key = uuid.uuid4()
        response = self.submit(token=invite["token"], key=key)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.submit(token=invite["token"]).status_code, 400)
        with patch("apps.users.registration_intake.timezone.now", return_value=invite["expires_at"] + timedelta(days=1)):
            retry = self.submit(token=invite["token"], key=key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(response.data, retry.data)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)
        self.assertEqual(StudentProfile.objects.count(), 1)
        self.assertEqual(self.staff_client.post(MANAGEMENT, {"action": "revoke_invite", "id": invite["id"]},
                                               format="json").status_code, 409)

    def test_changed_data_actor_or_invitation_cannot_reuse_key(self):
        invite, other = self.mint(), self.mint()
        key = uuid.uuid4()
        self.assertEqual(self.submit(token=invite["token"], key=key).status_code, 201)
        body = copy.deepcopy(self.body)
        body["payload"]["students"][0]["school"] = "Changed High"
        self.assertEqual(self.submit(body=body, token=invite["token"], key=key).status_code, 409)
        self.assertEqual(self.submit(token=other["token"], key=key).status_code, 409)
        self.assertEqual(self.submit(token=invite["token"], key=key, client=self.staff_client).status_code, 409)
        self.assertIsNone(RegistrationInvitation.objects.get(pk=other["id"]).used_at)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)

    def test_invalid_key_or_source_has_no_side_effects(self):
        invite = self.mint()
        for key in ("bad-key", ""):
            response = self.client.post(INTAKE, self.body, format="json", HTTP_IDEMPOTENCY_KEY=key,
                                        HTTP_X_REGISTRATION_INVITATION=invite["token"])
            self.assertEqual(response.status_code, 400)
        body = copy.deepcopy(self.body)
        body["payload"]["source"] = {"method": "supervisor_csv", "rowNumbers": [2]}
        self.assertEqual(self.submit(body=body, token=invite["token"]).status_code, 400)
        self.assert_not_consumed(invite)

    def test_anonymous_normalized_intake_requires_real_csrf_cookie_and_header(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(self.submit(client=client).status_code, 403)
        token = client.get("/api/v1/services/csrf/").json()["csrfToken"]
        response = client.post(INTAKE, self.body, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                               HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.data)

    def test_cross_origin_preflight_allows_gateway_headers(self):
        response = self.client.options(
            INTAKE, HTTP_ORIGIN="http://localhost:5173", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-csrftoken,idempotency-key,x-registration-invitation",
        )
        self.assertEqual(response.status_code, 200)
        allowed = response["Access-Control-Allow-Headers"]
        self.assertIn("idempotency-key", allowed)
        self.assertIn("x-registration-invitation", allowed)
        self.assertEqual(response["Access-Control-Allow-Credentials"], "true")

    def test_registration_aliases_share_gate_and_adapter(self):
        self.close_window()
        for url in (INTAKE, INTAKE + "/", "/api/v1/registration-intake/",
                    "/users/registration", "/users/registration/"):
            self.assertEqual(self.submit(url=url).status_code, 400)

    def test_atomic_guard_failure_rolls_back_student_and_receipt(self):
        invite = self.mint()
        def concurrent_revocation(*args, **kwargs):
            user = save_student(*args, **kwargs)
            RegistrationInvitation.objects.filter(pk=invite["id"]).update(revoked_at=timezone.now())
            return user
        with patch("apps.users.registration_intake.save_student", side_effect=concurrent_revocation):
            response = self.submit(token=invite["token"])
        self.assertEqual(response.status_code, 409)
        self.assert_not_consumed(invite)
        self.assertFalse(User.objects.filter(email="jordan.lee@example.com").exists())

    def test_atomic_database_failure_is_explicit_and_does_not_consume(self):
        invite = self.mint()
        with self.assertLogs("config.exception_handler", level="ERROR"), patch(
                   "apps.users.registration_intake.RegistrationSubmission.objects.create",
                   side_effect=IntegrityError("unexpected constraint")):
            response = self.submit(token=invite["token"])
        self.assertEqual(response.status_code, 500)
        self.assert_not_consumed(invite)

    def test_database_constraints_prevent_second_receipt_for_key_or_invitation(self):
        invite = self.mint()
        self.assertEqual(self.submit(token=invite["token"]).status_code, 201)
        previous = RegistrationSubmission.objects.get()
        another = User.objects.create_user(email="other@example.com", first_name="Other", last_name="Student")
        for key, invitation in ((previous.idempotency_key, None), (uuid.uuid4(), previous.invitation)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RegistrationSubmission.objects.create(
                    idempotency_key=key, invitation=invitation, request_digest="0" * 64,
                    window=self.window, student=another,
                )

    def test_rate_limit_still_applies_but_does_not_block_receipt_retry(self):
        key = uuid.uuid4()
        original = self.submit(key=key)
        cache.set("registration_ip:127.0.0.1", 10)
        self.assertEqual(self.submit().status_code, 429)
        retry = self.submit(key=key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data, original.data)


class SharedValidationTests(RegistrationSetup, TestCase):
    def warning_body(self):
        body = copy.deepcopy(self.body)
        student = body["payload"]["students"][0]
        student.update(firstName="William", lastName="Nixon", email="wiliam.nixon@example.com", school="USYD")
        KnownUniversity.objects.get_or_create(full_name="USYD")
        return body

    def test_all_soft_warnings_have_canonical_paths_and_do_not_burn_link(self):
        invite = self.mint()
        body = self.warning_body()
        response = self.submit(body=body, token=invite["token"])
        self.assertEqual(response.status_code, 400)
        warnings = response.data["warnings"]
        self.assertEqual(len(warnings), 2)
        self.assertEqual({warning["field"] for warning in warnings}, {"students.0.school", "students.0.email"})
        self.assertEqual({warning["override_field"] for warning in warnings}, {
            "students.0.overrides.ConfirmSchoolOverride", "students.0.overrides.ConfirmNameEmailOverride",
        })
        self.assertTrue(all(set(warning) == {"code", "field", "override_field", "message"} for warning in warnings))
        self.assert_not_consumed(invite)
        body["payload"]["students"][0]["overrides"] = {
            "ConfirmSchoolOverride": True, "ConfirmNameEmailOverride": True,
        }
        self.assertEqual(self.submit(body=body, token=invite["token"]).status_code, 201)

    def test_one_acknowledgement_does_not_override_the_other_warning(self):
        body = self.warning_body()
        body["payload"]["students"][0]["overrides"] = {"ConfirmSchoolOverride": True}
        response = self.submit(body=body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data["warnings"]), 1)
        self.assertEqual(response.data["warnings"][0]["field"], "students.0.email")

    def test_override_flags_are_boolean_and_allowlisted(self):
        invite = self.mint()
        for overrides in ({"ConfirmSchoolOverride": "true"}, {"ConfirmSchoolOverride": 1},
                          {"ConfirmSchoolOverride": None}, {"ApproveGuardian": True}):
            body = self.warning_body()
            body["payload"]["students"][0]["overrides"] = overrides
            response = self.submit(body=body, token=invite["token"])
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("warnings", response.data)
            self.assert_not_consumed(invite)

    def test_hard_errors_take_priority_over_warnings_and_confirmations(self):
        invite = self.mint()
        for change in ({"email": "invalid"}, {"yearLevel": "8"}, {"guardianDeferred": True},
                       {"guardian": {}}, {"is_staff": True}):
            body = self.warning_body()
            body["payload"]["students"][0].update(change)
            body["payload"]["students"][0]["overrides"] = {
                "ConfirmSchoolOverride": True, "ConfirmNameEmailOverride": True,
            }
            response = self.submit(body=body, token=invite["token"])
            self.assertEqual(response.status_code, 400, response.data)
            self.assertNotIn("warnings", response.data)
            self.assert_not_consumed(invite)

    def test_missing_guardian_email_and_identity_conflicts_are_hard_errors(self):
        invite = self.mint()
        for guardian in (
            {"firstName": "Taylor", "lastName": "Lee", "email": "", "relationship": "Parent"},
            {"firstName": "Jordan", "lastName": "Lee", "email": "other@example.com", "relationship": "Parent"},
            {"firstName": "Taylor", "lastName": "Lee", "email": "jordan.lee@example.com", "relationship": "Parent"},
        ):
            body = self.warning_body()
            # Match the student identity for this test, while retaining a university warning.
            body["payload"]["students"][0].update(firstName="Jordan", lastName="Lee", email="jordan.lee@example.com", guardian=guardian)
            response = self.submit(body=body, token=invite["token"])
            self.assertEqual(response.status_code, 400)
            self.assertIn("students.0.guardian.email", response.data["fields"])
            self.assertNotIn("warnings", response.data)
            self.assert_not_consumed(invite)

    def test_role_email_conflicts_cannot_be_overridden(self):
        invite = self.mint()
        existing = User.objects.create_user(email="teacher@example.com", first_name="Other", last_name="User")
        body = self.warning_body()
        body["payload"]["students"][0]["overrides"] = {"ConfirmSchoolOverride": True, "ConfirmNameEmailOverride": True}
        response = self.submit(body=body, token=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("supervisor.email", response.data["fields"])
        self.assertNotIn("warnings", response.data)
        self.assert_not_consumed(invite)
        RoleAssignmentHistory.objects.create(user=existing, role=Roles.objects.get(role_name="student"), valid_from=timezone.now())
        response = self.submit(body=body, token=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assert_not_consumed(invite)

    def test_supervisor_student_identity_conflict_is_hard(self):
        invite = self.mint()
        for supervisor in (
            {"firstName": "Jordan", "lastName": "Lee", "email": "teacher@example.com"},
            {"firstName": "Sam", "lastName": "Teacher", "email": "jordan.lee@example.com"},
        ):
            body = copy.deepcopy(self.body)
            body["payload"]["supervisor"] = supervisor
            response = self.submit(body=body, token=invite["token"])
            self.assertEqual(response.status_code, 400)
            self.assertIn("supervisor.email", response.data["fields"])
            self.assertNotIn("warnings", response.data)
            self.assert_not_consumed(invite)

    def test_existing_supervisor_email_cannot_be_registered_as_student(self):
        invite = self.mint()
        existing = User.objects.create_user(
            email="jordan.lee@example.com", first_name="Existing", last_name="Supervisor",
        )
        SupervisorProfile.objects.create(user=existing)
        response = self.submit(token=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("students.0.email", response.data["fields"])
        self.assertIn("supervisor", str(response.data["fields"]["students.0.email"]))
        self.assertNotIn("warnings", response.data)
        self.assert_not_consumed(invite)

    def test_a_student_may_register_without_a_supervisor(self):
        del self.body["payload"]["supervisor"]
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        row = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual(row.supervisor_details, {})
        self.assertFalse(StudentSupervisor.objects.exists())

    def test_a_nominated_supervisor_is_only_their_name_and_email(self):
        # No supervisor type or school any more: either is refused.
        for change in ({"supervisorMode": "school"}, {"supervisorMode": "parent"}):
            body = copy.deepcopy(self.body)
            body["payload"].update(change)
            self.assertEqual(self.submit(body=body).status_code, 400)
        body = copy.deepcopy(self.body)
        body["payload"]["supervisor"]["school"] = "Example High"
        self.assertEqual(self.submit(body=body).status_code, 400)

        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(RegistrationSubmission.objects.get().supervisor_details, {
            "firstName": "Sam", "lastName": "Teacher", "email": "teacher@example.com",
        })

    def test_shared_serializer_retains_represented_guardian_rules(self):
        from apps.users.registration_intake import validation_body
        student, supervisor = self.body["payload"]["students"][0], self.body["payload"]["supervisor"]
        body = validation_body(student, supervisor)
        for field in ("GuardianEmail", "GuardianName", "GuardianSurname"):
            body.pop(field)
        for registered_by, expected in (("Self", False), ("", False), ("Peer", True), ("Supervisor", True)):
            serializer = UserRegisterBodySerializer(data={**body, "RegisteredBy": registered_by})
            self.assertEqual(serializer.is_valid(), expected, serializer.errors)

    def test_known_university_alias_normalizes_and_legacy_serializer_uses_same_warning(self):
        KnownUniversity.objects.create(full_name="  Example   Institute ")
        self.assertTrue(KnownUniversity.matches(" example institute "))
        from apps.users.registration_intake import validation_body
        body = validation_body(self.body["payload"]["students"][0], self.body["payload"]["supervisor"])
        body["SchoolName"] = "EXAMPLE INSTITUTE"
        serializer = UserRegisterBodySerializer(data=body)
        self.assertFalse(serializer.is_valid())
        self.assertIn("looks like a university", str(serializer.errors))
        serializer = UserRegisterBodySerializer(data={**body, "ConfirmSchoolOverride": True})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class PhotoTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.root = self.enterContext(TemporaryDirectory(prefix="biotech-registration-test-"))
        self.enterContext(override_settings(MEDIA_ROOT=self.root, USE_AZURE_BLOB_STORAGE=False))
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

    def photo(self, colour="red"):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), colour).save(stream, format="PNG")
        return SimpleUploadedFile("portrait.png", stream.getvalue(), content_type="image/png")

    def upload(self, photo, *, token="", key=None, extra=None):
        return self.client.post(
            INTAKE, {"request": json.dumps(self.body), "students.0": photo, **(extra or {})},
            format="multipart", HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
            HTTP_X_REGISTRATION_INVITATION=token,
        )

    def test_existing_authenticated_photo_upload_keeps_replacement_and_url_contract(self):
        first = self.staff_client.post(
            "/api/v1/users/me/profile-image/", {"image": self.photo()}, format="multipart",
        )
        self.assertEqual(first.status_code, 200, first.data)
        self.staff.refresh_from_db()
        old_key = self.staff.profile_image_key
        self.assertTrue(get_profile_image_storage().exists(old_key))
        self.assertTrue(first.data["profile_image_url"].startswith("http://localhost:8000/media/"))

        second = self.staff_client.post(
            "/api/v1/users/me/profile-image/", {"image": self.photo("blue")}, format="multipart",
        )
        self.assertEqual(second.status_code, 200, second.data)
        self.staff.refresh_from_db()
        self.assertNotEqual(self.staff.profile_image_key, old_key)
        self.assertFalse(get_profile_image_storage().exists(old_key))
        self.assertTrue(get_profile_image_storage().exists(self.staff.profile_image_key))
        self.assertEqual(self.staff._meta.get_field("profile_image_key").max_length, 512)
        self.assertEqual(self.staff._meta.get_field("profile_image_content_type").max_length, 64)

    def test_someone_removes_their_own_photo(self):
        from apps.users.profile_images import save_profile_image
        old_key = save_profile_image(user=self.staff, uploaded_file=self.photo())

        response = self.staff_client.delete("/api/v1/users/me/profile-image/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["profile_image_url"])
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.profile_image_key, "")
        self.assertFalse(get_profile_image_storage().exists(old_key))
        # Again, with no photo left, is fine.
        self.assertEqual(self.staff_client.delete("/api/v1/users/me/profile-image/").status_code, 200)

    def test_invalid_replacement_preserves_the_existing_photo(self):
        from apps.users.profile_images import save_profile_image
        old_key = save_profile_image(user=self.staff, uploaded_file=self.photo())
        invalid = SimpleUploadedFile("fake.png", b"\x89PNG\r\n\x1a\nfake bytes", content_type="image/png")
        response = self.staff_client.post(
            "/api/v1/users/me/profile-image/", {"image": invalid}, format="multipart",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.profile_image_key, old_key)
        self.assertTrue(get_profile_image_storage().exists(old_key))

    def test_actual_photo_is_validated_saved_and_retry_does_not_duplicate(self):
        invite = self.mint()
        key = uuid.uuid4()
        first = self.upload(self.photo(), token=invite["token"], key=key)
        self.assertEqual(first.status_code, 201, first.data)
        student = StudentProfile.objects.get().user
        original_key = student.profile_image_key
        self.assertTrue(get_profile_image_storage().exists(original_key))
        self.assertEqual(student.profile_image_content_type, "image/png")
        self.assertIsNotNone(UserSerializer(student).data["profile_image_url"])
        second = self.upload(self.photo(), token=invite["token"], key=key)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data, second.data)
        student.refresh_from_db()
        self.assertEqual(student.profile_image_key, original_key)
        changed = self.upload(self.photo("blue"), token=invite["token"], key=key)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)

    def test_invalid_bytes_mime_size_and_duplicate_fields_do_not_burn_link(self):
        invite = self.mint()
        for photo in (
            SimpleUploadedFile("fake.png", b"\x89PNG\r\n\x1a\nfake bytes", content_type="image/png"),
            SimpleUploadedFile("fake.svg", b"<svg/>", content_type="image/svg+xml"),
            SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png"),
        ):
            response = self.upload(photo, token=invite["token"])
            self.assertEqual(response.status_code, 400)
            self.assertIsInstance(response.data["fields"]["students.0.profilePhoto"], list)
            self.assertIsInstance(response.data["fields"]["students.0.profilePhoto"][0], str)
            self.assertNotIn("warnings", response.data)
            self.assert_not_consumed(invite)
        response = self.upload([self.photo(), self.photo()], token=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assert_not_consumed(invite)
        response = self.upload(self.photo(), token=invite["token"], extra={"students.1": self.photo()})
        self.assertEqual(response.status_code, 400)
        self.assert_not_consumed(invite)

    def test_metadata_only_and_invalid_multipart_are_explicit_errors(self):
        self.body["payload"]["students"][0]["profilePhoto"] = {"name": "portrait.png", "type": "image/png", "size": 100}
        self.assertEqual(self.submit().status_code, 400)
        for value in ("not json", "[]", "null", '{"journey": "mentor", "payload": {}}',
                      json.dumps(self.body).replace('"Jordan"', "NaN")):
            response = self.client.post(INTAKE, {"request": value}, format="multipart",
                                        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(response.status_code, 400)

    def test_storage_failure_rolls_back_database_and_invitation(self):
        invite = self.mint()
        with self.assertLogs("config.exception_handler", level="ERROR"), patch(
            "apps.users.profile_images.get_profile_image_storage",
        ) as factory:
            factory.return_value.save.side_effect = OSError("test storage unavailable")
            response = self.upload(self.photo(), token=invite["token"])
        self.assertEqual(response.status_code, 500)
        self.assert_not_consumed(invite)

    def test_failed_image_metadata_save_removes_uploaded_blob(self):
        invite = self.mint()
        original = User.save
        storage = get_profile_image_storage()
        saved = []
        original_save = storage.save
        def save_blob(*args, **kwargs):
            key = original_save(*args, **kwargs)
            saved.append(key)
            return key
        def fail_image_metadata(user, *args, **kwargs):
            if "profile_image_key" in kwargs.get("update_fields", []):
                raise IntegrityError("test image metadata failure")
            return original(user, *args, **kwargs)
        with self.assertLogs("config.exception_handler", level="ERROR"), patch.object(
            storage, "save", side_effect=save_blob,
        ), patch.object(User, "save", fail_image_metadata):
            response = self.upload(self.photo(), token=invite["token"])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(saved), 1)
        self.assertFalse(storage.exists(saved[0]))
        self.assert_not_consumed(invite)


class LegacyTests(RegistrationSetup, TestCase):
    def legacy(self):
        return {"body": {
            "Title": "jordan.lee@example.com", "FirstName": "Jordan", "Surname": "Lee",
            "Country": "Australia", "Region": "NSW",
            "SupervisorEmail": "teacher@example.com", "SupervisorFirstName": "Sam", "SupervisorSurname": "Teacher",
            "GuardianEmail": "guardian@example.com", "GuardianName": "Taylor", "GuardianSurname": "Lee",
            "SchoolName": "Example High", "YearLevel": "10", "Areaofinterest": "Biotechnology",
        }}

    def test_legacy_wrapper_and_response_are_preserved(self):
        body = self.legacy()
        response = self.client.post(INTAKE, body, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, body["body"])
        self.assertEqual(StudentProfile.objects.count(), 1)
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())

    def test_legacy_cannot_bypass_window_or_self_guardian_validation(self):
        self.close_window()
        self.assertEqual(self.client.post(INTAKE, self.legacy(), format="json").status_code, 400)
        invite = self.mint()
        body = self.legacy()
        body["body"]["RegisteredBy"] = "Peer"
        body["body"].pop("GuardianEmail")
        response = self.client.post(INTAKE, body, format="json", HTTP_X_REGISTRATION_INVITATION=invite["token"])
        self.assertEqual(response.status_code, 400)
        self.assert_not_consumed(invite)

    def test_legacy_can_redeem_link_and_use_idempotency(self):
        self.close_window()
        invite = self.mint()
        body, key = self.legacy(), str(uuid.uuid4())
        first = self.client.post(INTAKE, body, format="json", HTTP_X_REGISTRATION_INVITATION=invite["token"],
                                 HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 200)
        retry = self.client.post(INTAKE, body, format="json", HTTP_X_REGISTRATION_INVITATION=invite["token"],
                                 HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["student_count"], 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)


class PostgreSQLRaceTests(RegistrationSetup, TransactionTestCase):
    """Run against an isolated PostgreSQL test DB to exercise actual row locks."""

    def race(self, requests):
        barrier = Barrier(len(requests))
        def send(args):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                client = APIClient()
                return client.post(INTAKE, args["body"], format="json",
                                   HTTP_X_REGISTRATION_INVITATION=args["token"],
                                   HTTP_IDEMPOTENCY_KEY=str(args["key"]))
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(send, requests))

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_identical_retries_create_exactly_one_student(self):
        invite = self.mint()
        args = {"body": self.body, "token": invite["token"], "key": uuid.uuid4()}
        results = self.race([args, args])
        self.assertEqual(sorted(result.status_code for result in results), [200, 201])
        self.assertEqual(results[0].data, results[1].data)
        self.assertEqual(StudentProfile.objects.count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_different_students_cannot_share_invitation(self):
        invite = self.mint()
        other = copy.deepcopy(self.body)
        other["payload"]["students"][0].update(firstName="Alex", email="alex.lee@example.com")
        results = self.race([
            {"body": self.body, "token": invite["token"], "key": uuid.uuid4()},
            {"body": other, "token": invite["token"], "key": uuid.uuid4()},
        ])
        self.assertEqual(sorted(result.status_code for result in results), [201, 400])
        self.assertEqual(StudentProfile.objects.count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_same_key_different_invitations_does_not_burn_second_link(self):
        first, second = self.mint(), self.mint()
        key = uuid.uuid4()
        results = self.race([
            {"body": self.body, "token": first["token"], "key": key},
            {"body": self.body, "token": second["token"], "key": key},
        ])
        self.assertEqual(sorted(result.status_code for result in results), [201, 409])
        self.assertEqual(RegistrationInvitation.objects.filter(used_at__isnull=False).count(), 1)
        self.assertEqual(RegistrationSubmission.objects.count(), 1)
        self.assertEqual(StudentProfile.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_revocation_and_redemption_have_one_consistent_winner(self):
        invite = self.mint()
        barrier = Barrier(2)
        session_cookie = self.staff_client.cookies["sessionid"].value
        def send(revoke):
            close_old_connections()
            try:
                client = APIClient()
                if revoke:
                    client.cookies["sessionid"] = session_cookie
                barrier.wait(timeout=10)
                if revoke:
                    return client.post(MANAGEMENT, {"action": "revoke_invite", "id": invite["id"]}, format="json")
                return client.post(INTAKE, self.body, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                                   HTTP_X_REGISTRATION_INVITATION=invite["token"])
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as workers:
            revoked, redeemed = list(workers.map(send, [True, False]))
        item = RegistrationInvitation.objects.get(pk=invite["id"])
        self.assertIn((revoked.status_code, redeemed.status_code), ((200, 400), (409, 201)))
        self.assertNotEqual(item.revoked_at is None, item.used_at is None)
        self.assertEqual(StudentProfile.objects.count(), int(item.used_at is not None))


class RegistrationDatesSetByTests(RegistrationSetup, TestCase):
    """Management > Registration > Registration Dates: who last saved them."""

    def test_saving_the_dates_records_who_set_them_and_when(self):
        self.assertEqual(self.staff_client.get(MANAGEMENT).data["window"]["set_by"], "")
        response = self.staff_client.post(MANAGEMENT, {
            "action": "window", "closes_at": (timezone.now() + timedelta(days=3)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["window"]["set_by"], "Staff Member")
        window = self.staff_client.get(MANAGEMENT).data["window"]
        self.assertEqual(window["set_by"], "Staff Member")
        self.assertIsNotNone(window["updated_at"])
