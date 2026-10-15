"""Single-student intake and staff-managed late links; no public role promotion."""
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
from rest_framework.exceptions import APIException, Throttled
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import is_admin
from apps.common.role_names import ROLE_STUDENT, get_role_by_name
from apps.common.storage import get_profile_image_storage
from apps.groups.models import Countries, CountryStates
from apps.resources.models import RoleAssignmentHistory
from .models import (
    AreasOfInterest, RegistrationInvitation, RegistrationSubmission, RegistrationWindow,
    StudentProfile, StudentSupervisor, SupervisorProfile, User, UserInterest,
)
from .profile_images import save_profile_image, validate_profile_image
from .serializers import (
    REGISTRATION_OVERRIDES, StrictBooleanField, UserRegisterBodySerializer,
    registration_warnings,
)


JOURNEY = "student_individual"
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
    school = serializers.CharField(max_length=255)
    yearLevel = serializers.ChoiceField(choices=["9", "10", "11", "12"])
    country = serializers.CharField(max_length=255)
    state = serializers.CharField(max_length=255, allow_blank=True, default="")
    interests = serializers.ListField(child=serializers.CharField(max_length=255), allow_empty=False, max_length=100)
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
        if data["guardianDeferred"]:
            errors["guardianDeferred"] = "A student registering themselves must provide guardian contact."
        if not self.context.get("legacy"):
            guardian = data["guardian"]
            if not guardian.get("relationship"):
                errors["guardian.relationship"] = "Choose the guardian's relationship."
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
    method = serializers.ChoiceField(choices=[JOURNEY])


class PayloadInput(StrictInput):
    students = StudentInput(many=True, min_length=1, max_length=1)
    source = SourceInput()
    supervisorMode = serializers.ChoiceField(choices=["school", "parent"], default="school")
    supervisor = SupervisorInput()

    def validate(self, data):
        if data["supervisorMode"] == "school" and not data["supervisor"]["school"] and not self.context.get("legacy"):
            raise serializers.ValidationError({"supervisor.school": "Enter the supervisor's school."})
        return data


class IntakeInput(StrictInput):
    journey = serializers.ChoiceField(choices=[JOURNEY])
    payload = PayloadInput()


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
        "student_count": 1, "created_at": submission.created_at.isoformat(),
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


def validation_body(student, supervisor):
    guardian = student["guardian"]
    return {
        "Title": student["email"], "FirstName": student["firstName"], "Surname": student["lastName"],
        "Country": student["country"], "Region": student["state"],
        "SchoolName": student["school"], "YearLevel": student["yearLevel"],
        "Areaofinterest": student["interests"][0],
        "GuardianEmail": guardian.get("email", ""), "GuardianName": guardian.get("firstName", ""),
        "GuardianSurname": guardian.get("lastName", ""),
        "SupervisorEmail": supervisor["email"], "SupervisorFirstName": supervisor["firstName"],
        "SupervisorSurname": supervisor["lastName"], "RegisteredBy": "Self",
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


def valid_invitation(token, window, now):
    if not token:
        return None
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
    country, state = resolve_location(student)
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
    profile = StudentProfile.objects.create(
        user=user, supervisor=sup, school_name=student["school"], year_lvl=student["yearLevel"],
        pg_first_name=guardian["firstName"], pg_last_name=guardian["lastName"],
        pg_email=guardian["email"].lower(), parent_guardian_flag=True,
        has_join_permission=False, joinperm_responseID=None,
        registered_by=registered_by,
    )
    if sup:
        StudentSupervisor.objects.create(
            student_user=profile, supervisor_user=sup,
            relationship_type="parent_guardian" if mode == "parent" else "teacher",
        )
    for description in dict.fromkeys(student["interests"]):
        interest, _ = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description, defaults={"interest_desc": description},
        )
        UserInterest.objects.get_or_create(user=user, interest=interest)
    return user


def register(request):
    raw = request.data
    if request.content_type.startswith("multipart/"):
        if len(raw.getlist("request")) != 1 or set(raw) - {"request", "students.0"}:
            raise serializers.ValidationError({"detail": "Supply one JSON request and at most one students.0 photo."})
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
    student = payload["students"][0]
    supervisor = payload["supervisor"]
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
    if set(request.FILES) - {"students.0"} or any(len(request.FILES.getlist(name)) != 1 for name in request.FILES):
        raise serializers.ValidationError({"detail": "Attach one photo using students.0."})
    photo = request.FILES.get("students.0")
    if photo:
        try:
            validate_profile_image(photo)
        except serializers.ValidationError as exc:
            detail = exc.detail.get("image", exc.detail) if isinstance(exc.detail, dict) else exc.detail
            raise serializers.ValidationError({
                "students.0.profilePhoto": detail if isinstance(detail, list) else [detail],
            })
    elif student["profilePhoto"] is not None:
        raise serializers.ValidationError({"students.0.profilePhoto": "Attach the actual image file, not only its metadata."})
    actor = request.user.pk if request.user.is_authenticated else None
    fingerprint = {
        "request": raw, "actor": actor, "invitation": token_hash(raw_token),
        "photo": hashlib.sha256(photo.read()).hexdigest() if photo else None,
    }
    if photo:
        photo.seek(0)
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
    created_file = None
    try:
        with transaction.atomic():
            # All intake and management writes lock the same year before the
            # invitation. Recheck idempotency after waiting for another writer.
            window = current_window(lock=True)
            previous = check_previous(key, digest)
            if previous:
                return Response(receipt(previous))
            now = timezone.now()
            invitation = valid_invitation(raw_token, window, now)
            if not window.is_open(now) and invitation is None:
                raise serializers.ValidationError({"detail": "Registration is closed. Contact an administrator for a late link."})
            body = validation_body(student, supervisor)
            validator = UserRegisterBodySerializer(
                data=body, context={"defer_warnings": True, "canonical_registration_fields": True},
            )
            if not validator.is_valid():
                raise serializers.ValidationError({
                    LEGACY_FIELDS.get(field, field): value if isinstance(value, list) else [value]
                    for field, value in validator.errors.items()
                })
            if payload["supervisorMode"] == "parent" and (
                supervisor["email"].casefold() != student["guardian"]["email"].casefold()
                or supervisor["firstName"].casefold() != student["guardian"]["firstName"].casefold()
                or supervisor["lastName"].casefold() != student["guardian"]["lastName"].casefold()
            ):
                raise serializers.ValidationError({"supervisor": "A parent supervisor must be the nominated guardian."})
            warnings = registration_warnings(validator.validated_data)
            if warnings:
                raise RegistrationWarnings([{
                    **warning, "field": LEGACY_FIELDS[warning["field"]],
                    "override_field": f"students.0.overrides.{warning['override_field']}",
                } for warning in warnings])
            from .views import _registered_by
            registered_by = _registered_by(raw["body"].get("RegisteredBy")) if legacy else StudentProfile.RegisteredBy.SELF
            user = save_student(
                student, supervisor, payload["supervisorMode"], now, registered_by=registered_by,
            )
            guardian = student["guardian"]
            submission = RegistrationSubmission.objects.create(
                idempotency_key=key, request_digest=digest, window=window, student=user,
                invitation=invitation, created_by=request.user if actor else None,
                supervisor_details=supervisor, supervisor_mode=payload["supervisorMode"],
                guardian_phone=guardian.get("phone", ""),
                guardian_relationship=guardian.get("relationshipOther") or guardian.get("relationship", ""),
                grouping_preference=student["groupingPreference"], source=payload["source"],
            )
            if invitation:
                updated = RegistrationInvitation.objects.filter(
                    pk=invitation.pk, used_at__isnull=True, revoked_at__isnull=True,
                    expires_at__gt=timezone.now(),
                ).update(used_at=timezone.now())
                if updated != 1:
                    raise RegistrationConflict("This late link is no longer available.")
            if photo:
                created_file = save_profile_image(user=user, uploaded_file=photo)
            response = raw["body"] if legacy else receipt(submission)
    except IntegrityError:
        if created_file:
            get_profile_image_storage().delete(created_file)
        previous = check_previous(key, digest)
        if previous:
            return Response(receipt(previous))
        if User.objects.filter(email__iexact=student["email"]).exists():
            raise serializers.ValidationError({"students.0.email": "An account with this email already exists."})
        raise
    except Exception:
        if created_file:
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
