"""Atomic student intake and staff-managed individual late links."""
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.core.signing import BadSignature, Signer
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, PermissionDenied, Throttled
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.common.rbac import is_admin, user_has_role
from apps.common.role_names import ROLE_STUDENT, ROLE_SUPERVISOR, get_role_by_name
from apps.common.storage import get_profile_image_storage
from apps.groups.models import Countries, CountryStates, GroupAutoNameUnavailable, GroupInterest, GroupMembership, Groups
from apps.groups.services import sync_supervisor_memberships_for_student
from apps.resources.models import RoleAssignmentHistory
from .models import (
    AreasOfInterest, RegistrationInvitation, RegistrationStudent, RegistrationSubmission, RegistrationWindow,
    StudentProfile, StudentSupervisor, SupervisorProfile, User, UserInterest,
)
from .profile_images import save_profile_image, validate_profile_image
from .serializers import (
    REGISTRATION_OVERRIDES, StrictBooleanField, UserRegisterBodySerializer,
    registration_warnings,
)


JOURNEY = "student_individual"
GROUP_JOURNEYS = {"student_team", "supervisor_group"}
SUPERVISOR_JOURNEYS = {"supervisor_individual", "supervisor_group", "supervisor_csv"}
STUDENT_JOURNEYS = [JOURNEY, "student_team", *sorted(SUPERVISOR_JOURNEYS)]
MAX_CSV_ROWS = 500
LEGACY_FIELDS = {
    "Title": "students.0.email", "FirstName": "students.0.firstName",
    "Surname": "students.0.lastName", "Country": "students.0.country",
    "Region": "students.0.state", "SchoolName": "students.0.school",
    "YearLevel": "students.0.yearLevel", "Areaofinterest": "students.0.interests",
    "GuardianEmail": "students.0.guardian.email",
    "GuardianName": "students.0.guardian.firstName",
    "GuardianSurname": "students.0.guardian.lastName",
    "SupervisorEmail": "supervisor.email", "SupervisorFirstName": "supervisor.firstName",
    "SupervisorSurname": "supervisor.lastName",
}


class RegistrationWarnings(serializers.ValidationError):
    default_code = "registration_warnings"

    def __init__(self, warnings):
        super().__init__("Please acknowledge the registration warnings before continuing.")
        self.extra = {"warnings": warnings}


class RegistrationConflict(APIException):
    status_code = 409
    default_code = "registration_conflict"
    default_detail = "Registration changed concurrently. Please retry the unchanged request."


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unknown registration field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class GuardianInput(StrictInput):
    firstName = serializers.CharField(max_length=255, allow_blank=True, default="")
    lastName = serializers.CharField(max_length=255, allow_blank=True, default="")
    email = serializers.EmailField(max_length=254, allow_blank=True, default="")
    phone = serializers.CharField(max_length=50, allow_blank=True, default="")
    relationship = serializers.ChoiceField(choices=["", "Parent", "Legal guardian", "Other"], default="")
    relationshipOther = serializers.CharField(max_length=255, allow_blank=True, default="")


class PhotoMetadataInput(StrictInput):
    name = serializers.CharField(max_length=255)
    type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=0, max_value=5 * 1024 * 1024)


class StudentInput(StrictInput):
    firstName = serializers.CharField(max_length=255)
    lastName = serializers.CharField(max_length=255)
    email = serializers.EmailField(max_length=254)
    school = serializers.CharField(max_length=255, allow_blank=True, default="")
    yearLevel = serializers.ChoiceField(choices=["", "9", "10", "11", "12"], default="")
    country = serializers.CharField(max_length=255, allow_blank=True, default="")
    state = serializers.CharField(max_length=255, allow_blank=True, default="")
    interests = serializers.ListField(child=serializers.CharField(max_length=255), max_length=100, default=list)
    guardian = GuardianInput(default=dict)
    guardianDeferred = StrictBooleanField(default=False)
    pronouns = serializers.CharField(max_length=100, allow_blank=True, default="")
    pronounsOther = serializers.CharField(max_length=100, allow_blank=True, default="")
    profilePhoto = PhotoMetadataInput(allow_null=True, default=None)
    groupingPreference = serializers.ChoiceField(choices=["", "school_only", "cross_school"], default="")
    overrides = serializers.DictField(child=StrictBooleanField(), default=dict)

    def validate_overrides(self, value):
        if set(value) - REGISTRATION_OVERRIDES:
            raise serializers.ValidationError("Unknown registration override.")
        return value

    def validate(self, data):
        errors = {}
        partial = self.context.get("partial_peer") and not any(
            data[field] for field in ("school", "yearLevel", "country")
        )
        if not partial:
            for field in ("school", "yearLevel", "country"):
                if not data[field]:
                    errors[field] = "This field is required."
        if self.context.get("group"):
            if data["interests"]:
                errors["interests"] = "Choose shared interests on the group, not individual members."
        elif not data["interests"]:
            errors["interests"] = "Choose at least one interest."
        optional_guardian = self.context.get("guardian_optional", False)
        if data["guardianDeferred"] and not optional_guardian:
            errors["guardianDeferred"] = "A student registering themselves must provide guardian contact."
        if data["guardianDeferred"] and any(data["guardian"].values()):
            errors["guardianDeferred"] = "Clear guardian details or turn off deferral."
        if not self.context.get("legacy"):
            guardian = data["guardian"]
            if not (optional_guardian and data["guardianDeferred"]):
                for field in ("firstName", "lastName", "email", "relationship"):
                    if not guardian.get(field):
                        errors[f"guardian.{field}"] = "This field is required."
                if guardian.get("relationship") == "Other" and not guardian.get("relationshipOther"):
                    errors["guardian.relationshipOther"] = "Enter the guardian's relationship."
            if data["country"].casefold() == "australia" and not data["state"]:
                errors["state"] = "Choose your state or territory."
        if data["pronouns"] == "Other" and not data["pronounsOther"]:
            errors["pronounsOther"] = "Enter your pronouns."
        if errors:
            raise serializers.ValidationError(errors)
        data["email"] = data["email"].lower()
        return data


class SupervisorInput(StrictInput):
    firstName = serializers.CharField(max_length=255)
    lastName = serializers.CharField(max_length=255)
    email = serializers.EmailField(max_length=254)
    school = serializers.CharField(max_length=255, allow_blank=True, default="")


class SourceInput(StrictInput):
    method = serializers.ChoiceField(choices=STUDENT_JOURNEYS)
    fileName = serializers.CharField(max_length=255, required=False)
    rowNumbers = serializers.ListField(
        child=serializers.IntegerField(min_value=2), max_length=MAX_CSV_ROWS, required=False,
    )


class GroupInput(StrictInput):
    interests = serializers.ListField(
        child=serializers.CharField(max_length=255), allow_empty=False, max_length=100,
    )


class PayloadInput(StrictInput):
    students = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=MAX_CSV_ROWS,
    )
    source = SourceInput()
    supervisorMode = serializers.ChoiceField(choices=["school", "parent"], default="school")
    supervisor = SupervisorInput(required=False)
    group = GroupInput(required=False)


class IntakeInput(StrictInput):
    journey = serializers.ChoiceField(choices=STUDENT_JOURNEYS)
    payload = PayloadInput()

    def validate(self, data):
        journey, payload = data["journey"], data["payload"]
        errors = {}
        count = len(payload["students"])
        if journey in GROUP_JOURNEYS:
            if not 2 <= count <= 5:
                errors["payload.students"] = "A group must contain two to five students."
            if "group" not in payload:
                errors["payload.group.interests"] = "Choose shared group interests."
        else:
            if "group" in payload:
                errors["payload.group"] = "This journey does not create a group."
            if journey != "supervisor_csv" and count != 1:
                errors["payload.students"] = "This journey registers one student."
        source = payload["source"]
        if source["method"] != journey:
            errors["payload.source.method"] = "Source method must match the journey."
        if journey == "supervisor_csv":
            rows = source.get("rowNumbers", [])
            if not source.get("fileName") or len(rows) != count or rows != sorted(set(rows)):
                errors["payload.source.rowNumbers"] = "Provide the filename and one unique ordered CSV row number per student."
        elif set(source) - {"method"}:
            errors["payload.source"] = "CSV metadata is only accepted for CSV intake."
        if journey in SUPERVISOR_JOURNEYS:
            if "supervisor" in payload or payload["supervisorMode"] != "school":
                errors["payload.supervisor"] = "Supervisor identity comes from the authenticated session."
        elif "supervisor" not in payload:
            errors["payload.supervisor"] = "Nominate a supervisor."
        elif payload["supervisorMode"] == "school" and not payload["supervisor"]["school"] and not self.context.get("legacy"):
            errors["payload.supervisor.school"] = "Enter the supervisor's school."
        students = []
        emails = {}
        for index, raw in enumerate(payload["students"]):
            parser = StudentInput(data=raw, context={
                **self.context,
                "partial_peer": journey == "student_team" and index > 0,
                "guardian_optional": journey in SUPERVISOR_JOURNEYS or (journey == "student_team" and index > 0),
                "group": journey in GROUP_JOURNEYS,
            })
            if not parser.is_valid():
                errors.update(error_fields(parser.errors, f"payload.students.{index}"))
                continue
            student = parser.validated_data
            students.append(student)
            email = student["email"]
            if email in emails:
                for duplicate in (emails[email], index):
                    errors[f"payload.students.{duplicate}.email"] = "A student email appears more than once."
            emails[email] = index
        if errors:
            raise serializers.ValidationError(errors)
        for index, student in enumerate(students):
            if student["guardian"].get("email", "").lower() in emails:
                errors[f"payload.students.{index}.guardian.email"] = "A registered student cannot be listed as a guardian."
        if errors:
            raise serializers.ValidationError(errors)
        payload["students"] = students
        return data


class WindowInput(serializers.ModelSerializer):
    class Meta:
        model = RegistrationWindow
        fields = ["year", "opens_at", "closes_at"]

    def validate(self, data):
        if data.get("year", self.instance.year) != self.instance.year:
            raise serializers.ValidationError({"year": "Manage the current registration year."})
        opens = data.get("opens_at", self.instance.opens_at)
        closes = data.get("closes_at", self.instance.closes_at)
        if opens and closes and opens >= closes:
            raise serializers.ValidationError({"closes_at": "Closing must be after opening."})
        return data


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def invitation_signer():
    return Signer(salt="registration-invitation", fallback_keys=[])


def invitation_token(invitation):
    value = f"{invitation.nonce}:{invitation.window_id}:{invitation.journey}"
    return invitation_signer().sign(value)


def invitation_payload(invitation, now):
    token = invitation_token(invitation)
    recoverable = hmac.compare_digest(token_hash(token), invitation.token_hash)
    return {
        "id": invitation.pk, "journey": invitation.journey,
        "created_at": invitation.created_at, "expires_at": invitation.expires_at,
        "revoked_at": invitation.revoked_at, "used_at": invitation.used_at,
        "status": invitation.status_at(now) if recoverable else "signing_key_changed",
        "token": token if recoverable else None,
        "url": f"{settings.FRONTEND_BASE_URL.rstrip('/')}/#/register?invite={quote(token, safe='')}" if recoverable else None,
    }


def receipt(submission):
    return {
        "reference_code": str(submission.reference), "journey": submission.journey,
        "student_count": submission.student_count, "created_at": submission.created_at.isoformat(),
    }


def error_fields(error, prefix=""):
    result = {}
    if isinstance(error, dict):
        for field, value in error.items():
            path = f"{prefix}.{field}" if prefix else str(field)
            result.update(error_fields(value, path))
    elif isinstance(error, list) and error and isinstance(error[0], dict):
        for index, value in enumerate(error):
            result.update(error_fields(value, f"{prefix}.{index}"))
    else:
        result[prefix] = error if isinstance(error, list) else [error]
    return result


def legacy_request(body):
    if not isinstance(body, dict):
        raise serializers.ValidationError({"body": "Provide the registration body."})
    unknown = set(body) - set(UserRegisterBodySerializer().fields)
    if unknown:
        raise serializers.ValidationError({key: "Unknown registration field." for key in sorted(unknown)})
    return {
        "journey": JOURNEY,
        "payload": {
            "students": [{
                "email": body.get("Title", ""), "firstName": body.get("FirstName", ""),
                "lastName": body.get("Surname", ""), "country": body.get("Country", ""),
                "state": body.get("Region", ""), "school": body.get("SchoolName", ""),
                "yearLevel": body.get("YearLevel", ""), "interests": [body.get("Areaofinterest", "")],
                "guardian": {
                    "email": body.get("GuardianEmail", ""), "firstName": body.get("GuardianName", ""),
                    "lastName": body.get("GuardianSurname", ""),
                },
                "overrides": {key: body[key] for key in REGISTRATION_OVERRIDES if key in body},
            }],
            "source": {"method": JOURNEY}, "supervisorMode": "school",
            "supervisor": {
                "email": body.get("SupervisorEmail", ""), "firstName": body.get("SupervisorFirstName", ""),
                "lastName": body.get("SupervisorSurname", ""), "school": body.get("SchoolName", ""),
            },
        },
    }


def validation_body(student, supervisor, *, registered_by="self", group_interests=()):
    guardian = student["guardian"]
    return {
        "Title": student["email"], "FirstName": student["firstName"], "Surname": student["lastName"],
        "Country": student["country"], "Region": student["state"],
        "SchoolName": student["school"], "YearLevel": student["yearLevel"],
        "Areaofinterest": next(iter(student["interests"] or group_interests), ""),
        "GuardianEmail": guardian.get("email", ""), "GuardianName": guardian.get("firstName", ""),
        "GuardianSurname": guardian.get("lastName", ""),
        "SupervisorEmail": supervisor["email"], "SupervisorFirstName": supervisor["firstName"],
        "SupervisorSurname": supervisor["lastName"], "RegisteredBy": registered_by,
        **student["overrides"],
    }


def check_previous(key, digest):
    previous = RegistrationSubmission.objects.filter(idempotency_key=key).first()
    if previous is not None and not hmac.compare_digest(previous.request_digest, digest):
        raise RegistrationConflict("Use a new Idempotency-Key for changed registration details or identity.")
    return previous


def current_window(*, lock=False):
    window, _ = RegistrationWindow.objects.get_or_create(year=timezone.now().year)
    if lock:
        window = RegistrationWindow.objects.select_for_update().get(pk=window.pk)
    return window


def valid_invitation(token, window, now, *, journey=JOURNEY):
    if not token:
        return None
    if journey != JOURNEY:
        raise serializers.ValidationError({"detail": "Late links permit only individual student registration."})
    message = {"detail": "This registration link is invalid, expired, revoked or already used."}
    if len(token) > 256:
        raise serializers.ValidationError(message)
    try:
        invitation_signer().unsign(token)
    except BadSignature:
        raise serializers.ValidationError(message)
    invitation = RegistrationInvitation.objects.select_for_update().filter(
        token_hash=token_hash(token), window=window, journey=JOURNEY,
        revoked_at__isnull=True, used_at__isnull=True, expires_at__gt=now,
    ).first()
    if invitation is None:
        raise serializers.ValidationError(message)
    return invitation


def resolve_location(student):
    country, _ = Countries.objects.get_or_create(
        country_name__iexact=student["country"], defaults={"country_name": student["country"]},
    )
    state = None
    region = student["state"]
    if region and region.casefold() != country.country_name.casefold():
        state, _ = CountryStates.objects.get_or_create(
            country=country, state_name__iexact=region, defaults={"state_name": region},
        )
    return country, state


def save_student(student, supervisor, mode, now, *, registered_by):
    country, state = resolve_location(student) if student["country"] else (None, None)
    user = User.objects.create_user(
        email=student["email"], first_name=student["firstName"], last_name=student["lastName"],
        country=country, state=state,
        pronouns=student["pronounsOther"] if student["pronouns"] == "Other" else student["pronouns"],
    )
    RoleAssignmentHistory.objects.create(
        user=user, role=get_role_by_name(ROLE_STUDENT), valid_from=now,
        valid_to=now + timedelta(weeks=6),
    )
    # Nomination is not a supervisor invitation or a role grant. Only link an
    # already-provisioned profile; preserve all existing account details.
    sup = SupervisorProfile.objects.filter(user__email__iexact=supervisor["email"]).first()
    guardian = student["guardian"]
    has_guardian = all(guardian.get(field) for field in ("firstName", "lastName", "email"))
    profile = StudentProfile.objects.create(
        user=user, supervisor=sup, school_name=student["school"], year_lvl=student["yearLevel"],
        pg_first_name=guardian.get("firstName", ""), pg_last_name=guardian.get("lastName", ""),
        pg_email=guardian.get("email", "").lower() or None, parent_guardian_flag=has_guardian,
        has_join_permission=False, joinperm_responseID=None,
        registered_by=registered_by,
    )
    if sup:
        relationship = StudentSupervisor.RelationshipTypeChoices.TEACHER
        if mode == "parent":
            relationship = (
                StudentSupervisor.RelationshipTypeChoices.PARENT_GUARDIAN
                if supervisor["email"].casefold() == guardian.get("email", "").casefold()
                else StudentSupervisor.RelationshipTypeChoices.OTHER
            )
        StudentSupervisor.objects.create(
            student_user=profile, supervisor_user=sup,
            relationship_type=relationship,
        )
    for description in dict.fromkeys(student["interests"]):
        interest, _ = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description, defaults={"interest_desc": description},
        )
        UserInterest.objects.get_or_create(user=user, interest=interest)
    return user


def authenticated_supervisor(request):
    user = request.user
    if (
        not user.is_authenticated or user.account_status in User.INACTIVE_LOGIN_STATUSES
        or not (user_has_role(user, ROLE_SUPERVISOR) or is_admin(user) or user.is_staff or user.is_superuser)
    ):
        raise PermissionDenied("An authenticated current supervisor is required.")
    profile = SupervisorProfile.objects.filter(user=user).first()
    if profile is None:
        raise PermissionDenied("An existing supervisor profile is required.")
    return {
        "firstName": user.first_name, "lastName": user.last_name,
        "email": user.email, "school": profile.school_name,
    }


def registration_field(field, index):
    return LEGACY_FIELDS.get(field, field).replace("students.0.", f"students.{index}.")


def participant_details(student):
    guardian = student["guardian"]
    return {
        "guardian_phone": guardian.get("phone", ""),
        "guardian_relationship": guardian.get("relationshipOther") or guardian.get("relationship", ""),
        "grouping_preference": student["groupingPreference"],
    }


def save_group(users, payload, actor):
    try:
        group = Groups.create_auto_named()
    except GroupAutoNameUnavailable as exc:
        raise RegistrationConflict(str(exc)) from exc
    GroupMembership.objects.bulk_create([
        GroupMembership(
            group=group, user=user, membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        ) for user in users
    ])
    for description in dict.fromkeys(payload["group"]["interests"]):
        interest, _ = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description, defaults={"interest_desc": description},
        )
        GroupInterest.objects.get_or_create(group=group, interest=interest)
    sync_supervisor_memberships_for_student(users[0].pk)
    log_audit_event(
        actor=actor, entity_type="group", entity_id=group.pk, action="registration",
        after_state={"group_name": group.group_name, "student_ids": [user.pk for user in users]},
    )
    return group


def register(request):
    raw = request.data
    if request.content_type.startswith("multipart/"):
        if len(raw.getlist("request")) != 1 or set(raw) - {"request"} - set(request.FILES):
            raise serializers.ValidationError({"detail": "Supply one JSON request and indexed student photo files."})
        try:
            raw = json.loads(raw["request"], parse_constant=reject_json_constant)
        except (ValueError, TypeError):
            raise serializers.ValidationError({"detail": "Invalid registration request JSON."})
    if not isinstance(raw, dict):
        raise serializers.ValidationError({"detail": "Provide a registration object."})
    legacy = "body" in raw and "journey" not in raw
    if legacy and set(raw) != {"body"}:
        raise serializers.ValidationError({"detail": "Provide only the legacy body wrapper."})
    if not legacy:
        SessionAuthentication().enforce_csrf(request)
    envelope = legacy_request(raw["body"]) if legacy else raw
    parser = IntakeInput(data=envelope, context={"legacy": legacy})
    if not parser.is_valid():
        errors = error_fields(parser.errors)
        errors = {key.removeprefix("payload."): value for key, value in errors.items()}
        raise serializers.ValidationError(errors)
    payload = parser.validated_data["payload"]
    journey = parser.validated_data["journey"]
    students = payload["students"]
    supervisor = authenticated_supervisor(request) if journey in SUPERVISOR_JOURNEYS else payload["supervisor"]
    raw_token = request.headers.get("X-Registration-Invitation", "")
    key_value = request.headers.get("Idempotency-Key")
    try:
        key = uuid.UUID(key_value) if key_value and len(key_value) <= 64 else None
    except (ValueError, AttributeError):
        key = None
    if key is None:
        if not legacy or key_value:
            raise serializers.ValidationError({"detail": "A valid UUID Idempotency-Key is required."})
        key = uuid.uuid4()
    if set(request.FILES) - {f"students.{i}" for i in range(len(students))} or any(
        len(request.FILES.getlist(name)) != 1 for name in request.FILES
    ):
        raise serializers.ValidationError({"detail": "Attach at most one photo per indexed student."})
    photos = [request.FILES.get(f"students.{i}") for i in range(len(students))]
    photo_digests = []
    for index, (student, photo) in enumerate(zip(students, photos)):
        if photo:
            try:
                validate_profile_image(photo)
            except serializers.ValidationError as exc:
                detail = exc.detail.get("image", exc.detail) if isinstance(exc.detail, dict) else exc.detail
                raise serializers.ValidationError({
                    f"students.{index}.profilePhoto": detail if isinstance(detail, list) else [detail],
                })
        elif student["profilePhoto"] is not None:
            raise serializers.ValidationError({
                f"students.{index}.profilePhoto": ["Attach the actual image file, not only its metadata."],
            })
        photo_digests.append(hashlib.sha256(photo.read()).hexdigest() if photo else None)
        if photo:
            photo.seek(0)
    actor = request.user.pk if request.user.is_authenticated else None
    fingerprint = {
        "request": raw, "actor": actor, "invitation": token_hash(raw_token),
        **({"photo": photo_digests[0]} if len(students) == 1 else {"photos": photo_digests}),
    }
    digest = token_hash(json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), allow_nan=False))
    previous = check_previous(key, digest)
    if previous:
        return Response(receipt(previous))
    from .views import _client_ip, REGISTRATION_PER_IP_LIMIT, REGISTRATION_WINDOW_SECONDS
    rate_key = f"registration_ip:{_client_ip(request)}"
    attempts = cache.get(rate_key, 0)
    if attempts >= REGISTRATION_PER_IP_LIMIT:
        raise Throttled(wait=REGISTRATION_WINDOW_SECONDS)
    cache.set(rate_key, attempts + 1, REGISTRATION_WINDOW_SECONDS)
    created_files = []
    try:
        with transaction.atomic():
            # All intake and management writes lock the same year before the
            # invitation. Recheck idempotency after waiting for another writer.
            window = current_window(lock=True)
            previous = check_previous(key, digest)
            if previous:
                return Response(receipt(previous))
            now = timezone.now()
            invitation = valid_invitation(raw_token, window, now, journey=journey)
            if not window.is_open(now) and invitation is None:
                raise serializers.ValidationError({"detail": "Registration is closed. Contact an administrator for a late link."})
            errors, warnings, provenance = {}, [], []
            for index, student in enumerate(students):
                registered_by = (
                    StudentProfile.RegisteredBy.SUPERVISOR if journey in SUPERVISOR_JOURNEYS
                    else StudentProfile.RegisteredBy.PEER if index else StudentProfile.RegisteredBy.SELF
                )
                provenance.append(registered_by)
                validator = UserRegisterBodySerializer(
                    data=validation_body(
                        student, supervisor, registered_by=registered_by,
                        group_interests=payload.get("group", {}).get("interests", []),
                    ),
                    context={
                        "defer_warnings": True, "canonical_registration_fields": True,
                        "allow_partial_student": registered_by == StudentProfile.RegisteredBy.PEER,
                    },
                )
                if not validator.is_valid():
                    errors.update({
                        registration_field(field, index): value if isinstance(value, list) else [value]
                        for field, value in validator.errors.items()
                    })
                    continue
                warnings.extend([{
                    **warning, "field": registration_field(warning["field"], index),
                    "override_field": f"students.{index}.overrides.{warning['override_field']}",
                } for warning in registration_warnings(validator.validated_data)])
            if errors:
                raise serializers.ValidationError(errors)
            student = students[0]
            if payload["supervisorMode"] == "parent" and (
                supervisor["email"].casefold() != student["guardian"]["email"].casefold()
                or supervisor["firstName"].casefold() != student["guardian"]["firstName"].casefold()
                or supervisor["lastName"].casefold() != student["guardian"]["lastName"].casefold()
            ):
                raise serializers.ValidationError({"supervisor": ["A parent supervisor must be the nominated guardian."]})
            if warnings:
                raise RegistrationWarnings(warnings)
            from .views import _registered_by
            if legacy:
                provenance[0] = _registered_by(raw["body"].get("RegisteredBy"))
            users = [
                save_student(item, supervisor, payload["supervisorMode"], now, registered_by=registered_by)
                for item, registered_by in zip(students, provenance)
            ]
            actor_user = request.user if actor else None
            group = save_group(users, payload, actor_user) if journey in GROUP_JOURNEYS else None
            submission = RegistrationSubmission.objects.create(
                idempotency_key=key, request_digest=digest, window=window, student=users[0],
                student_count=len(users), journey=journey, group=group,
                invitation=invitation, created_by=actor_user,
                supervisor_details=supervisor, supervisor_mode=payload["supervisorMode"],
                source=payload["source"], **participant_details(students[0]),
            )
            RegistrationStudent.objects.bulk_create([
                RegistrationStudent(
                    submission=submission, student=user, position=index, **participant_details(item),
                ) for index, (user, item) in enumerate(zip(users, students))
            ])
            if invitation:
                updated = RegistrationInvitation.objects.filter(
                    pk=invitation.pk, used_at__isnull=True, revoked_at__isnull=True,
                    expires_at__gt=timezone.now(),
                ).update(used_at=timezone.now())
                if updated != 1:
                    raise RegistrationConflict("This late link is no longer available.")
            for user, photo in zip(users, photos):
                if photo:
                    created_files.append(save_profile_image(user=user, uploaded_file=photo))
            response = raw["body"] if legacy else receipt(submission)
    except IntegrityError:
        for created_file in created_files:
            get_profile_image_storage().delete(created_file)
        previous = check_previous(key, digest)
        if previous:
            return Response(receipt(previous))
        duplicates = {
            f"students.{index}.email": ["An account with this email already exists."]
            for index, student in enumerate(students)
            if User.objects.filter(email__iexact=student["email"]).exists()
        }
        if duplicates:
            raise serializers.ValidationError(duplicates)
        raise
    except Exception:
        for created_file in created_files:
            get_profile_image_storage().delete(created_file)
        raise
    return Response(response, status=200 if legacy else 201)


def reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


class RegistrationIntakeView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser, MultiPartParser]

    def get(self, request):
        return Response(WindowInput(current_window()).data)

    def post(self, request):
        return register(request)


class RegistrationStatesView(APIView):
    """GET ?country=Australia: that country's states as the database holds
    them (Australia's loaded by groups' 0013 migration), for the registration
    form's dropdown. Open to anyone, as registration is."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        country = (request.query_params.get("country") or "").strip()
        states = (
            CountryStates.objects.filter(country__country_name__iexact=country)
            .order_by("state_name")
            .values_list("state_name", flat=True)
            .distinct()
            if country
            else []
        )
        return Response({"states": list(states)})


class IsRegistrationManager(permissions.BasePermission):
    message = "Staff or administrator permission is required."

    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated and user.account_status not in User.INACTIVE_LOGIN_STATUSES
            and (user.is_staff or user.is_superuser or is_admin(user))
        )


class RegistrationManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRegistrationManager]
    authentication_classes = [SessionAuthentication]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get(self, request):
        window = current_window()
        try:
            page = serializers.IntegerField(min_value=1).run_validation(request.query_params.get("page", 1))
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"page": exc.detail})
        invitations = RegistrationInvitation.objects.filter(window=window).order_by("-created_at", "-id")
        now = timezone.now()
        return Response({
            "window": WindowInput(window).data,
            "count": invitations.count(), "page": page,
            "invitations": [invitation_payload(item, now) for item in invitations[(page - 1) * 100:page * 100]],
        })

    def post(self, request):
        if not isinstance(request.data, dict):
            raise serializers.ValidationError({"detail": "Provide a management action."})
        action = request.data.get("action")
        allowed = {
            "window": {"action", "year", "opens_at", "closes_at"},
            "invite": {"action", "expires_at"},
            "revoke_invite": {"action", "id"},
        }
        if not isinstance(action, str) or action not in allowed:
            raise serializers.ValidationError({"action": "Choose window, invite or revoke_invite."})
        if set(request.data) - allowed[action]:
            raise serializers.ValidationError({"detail": "Unknown management field."})
        with transaction.atomic():
            window = current_window(lock=True)
            if action == "window":
                serializer = WindowInput(window, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response({"window": serializer.data})
            if action == "invite":
                try:
                    expires = serializers.DateTimeField().run_validation(request.data.get("expires_at"))
                except serializers.ValidationError as exc:
                    raise serializers.ValidationError({"expires_at": exc.detail})
                if expires <= timezone.now():
                    raise serializers.ValidationError({"expires_at": "Choose a future expiry."})
                item = RegistrationInvitation(
                    window=window, expires_at=expires, created_by=request.user,
                )
                item.token_hash = token_hash(invitation_token(item))
                item.save()
                return Response(invitation_payload(item, timezone.now()), status=201)
            try:
                pk = serializers.IntegerField(min_value=1).run_validation(request.data.get("id"))
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"id": exc.detail})
            invitation = get_object_or_404(
                RegistrationInvitation.objects.select_for_update(), pk=pk, window=window,
            )
            if invitation.used_at is not None:
                raise RegistrationConflict("A used link cannot be revoked.")
            if invitation.revoked_at is None:
                invitation.revoked_at = timezone.now()
                invitation.save(update_fields=["revoked_at"])
            return Response(invitation_payload(invitation, timezone.now()))
