"""A supervisor (a teacher, usually) registering on the public registration
page (``journey: "supervisor"``): their contact details, their school, whether
they're a teacher or a parent, where they are, and (as a student may) their
pronouns and a profile photo.

As a mentor registers (``apps.users.mentor_registration``), but active at once:
an account with the supervisor role and a supervisor profile, which signs in
as any other to register their students. This year's students who named
their email as their supervisor before it was a supervisor's become theirs.
As for a mentor, the registration dates apply (late links stay student only),
an email with an account is refused, the same request sent again gets the
same receipt (its Idempotency-Key), and a registration email is sent once
it's saved (``registration_new_supervisor``). A photo comes as a student's
does: the JSON in a multipart ``request``, the file as ``supervisor``.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import Throttled
from rest_framework.response import Response

from apps.common.role_names import ROLE_SUPERVISOR, get_role_by_name
from apps.common.storage import get_profile_image_storage
from apps.groups.services import sync_supervisor_memberships
from apps.resources.models import RoleAssignmentHistory

from .models import (
    RegistrationStudent, RegistrationSubmission, StudentProfile, StudentSupervisor, SupervisorProfile, User,
)
from .profile_images import save_profile_image, validate_profile_image
from .registration_intake import (
    PhotoMetadataInput, StrictInput, check_previous, current_window, error_fields, receipt, require_policies,
    resolve_location, token_hash,
    valid_invitation,
)

JOURNEY = "supervisor"
# The file field a supervisor's photo comes in.
PHOTO = "supervisor"
# Teacher or parent, kept on their registration as a student's nominated
# supervisor's is (``RegistrationSubmission.supervisor_mode``).
MODES = {"teacher": "school", "parent": "parent"}


class SupervisorInput(StrictInput):
    firstName = serializers.CharField(max_length=150)
    lastName = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    school = serializers.CharField(max_length=255)
    relationship = serializers.ChoiceField(choices=tuple(MODES))
    country = serializers.CharField(max_length=255)
    state = serializers.CharField(max_length=255, allow_blank=True, default="")
    pronouns = serializers.CharField(max_length=100, allow_blank=True, default="")
    pronounsOther = serializers.CharField(max_length=100, allow_blank=True, default="")
    profilePhoto = PhotoMetadataInput(allow_null=True, default=None)

    def validate(self, data):
        errors = {}
        if data["country"].casefold() == "australia" and not data["state"]:
            errors["state"] = "Choose your state or territory."
        if data["pronouns"] == "Other" and not data["pronounsOther"]:
            errors["pronounsOther"] = "Enter your pronouns."
        if errors:
            raise serializers.ValidationError(errors)
        data["email"] = data["email"].lower()
        return data


class SupervisorPayloadInput(StrictInput):
    supervisor = SupervisorInput()


class SupervisorIntakeInput(StrictInput):
    journey = serializers.ChoiceField(choices=[JOURNEY])
    payload = SupervisorPayloadInput()
    # The BIOTech Futures policies, ticked on the form's last step: needed.
    policiesAgreed = serializers.BooleanField(required=False, default=False)


def save_supervisor(supervisor: dict, now) -> User:
    """The supervisor's account, active at once, with the supervisor role and
    profile (their school)."""
    country, state = resolve_location(supervisor)
    user = User.objects.create_user(
        email=supervisor["email"], first_name=supervisor["firstName"], last_name=supervisor["lastName"],
        country=country, state=state,
        pronouns=supervisor["pronounsOther"] if supervisor["pronouns"] == "Other" else supervisor["pronouns"],
        account_status=User.AccountStatus.ACTIVE, is_active=True, activated_at=now,
    )
    RoleAssignmentHistory.objects.create(
        user=user, role=get_role_by_name(ROLE_SUPERVISOR), valid_from=now, valid_to=None,
    )
    SupervisorProfile.objects.create(user=user, school_name=supervisor["school"])
    return user


def link_nominating_students(profile: SupervisorProfile, window, relationship: str) -> int:
    """This year's students who named this supervisor's email when they
    registered, before it was a supervisor's: theirs now, as registering would
    have made them had it been, as their teacher or their parent
    (``relationship``). A student with a supervisor keeps theirs. How many
    were linked."""
    submissions = RegistrationSubmission.objects.filter(
        window=window, supervisor_details__email__iexact=profile.user.email,
    )
    student_ids = set(submissions.values_list("student_id", flat=True))
    student_ids.update(
        RegistrationStudent.objects.filter(submission__in=submissions).values_list("student_id", flat=True)
    )
    students = list(StudentProfile.objects.filter(user_id__in=student_ids, supervisor__isnull=True))
    relationship_type = (
        StudentSupervisor.RelationshipTypeChoices.PARENT_GUARDIAN if relationship == "parent"
        else StudentSupervisor.RelationshipTypeChoices.TEACHER
    )
    for student in students:
        student.supervisor = profile
        student.save(update_fields=["supervisor"])
        StudentSupervisor.objects.get_or_create(
            student_user=student, supervisor_user=profile, defaults={"relationship_type": relationship_type},
        )
    if students:
        sync_supervisor_memberships(profile.pk)
    return len(students)


def _taken() -> serializers.ValidationError:
    return serializers.ValidationError({"supervisor.email": ["An account with this email already exists."]})


def _photo(request, supervisor: dict):
    """Their photo, checked as a student's is: one file, the image itself, as
    its metadata says. None when there's none."""
    if set(request.FILES) - {PHOTO} or len(request.FILES.getlist(PHOTO)) > 1:
        raise serializers.ValidationError({"detail": "Attach at most one photo, as supervisor."})
    photo = request.FILES.get(PHOTO)
    if photo is None:
        if supervisor["profilePhoto"] is not None:
            raise serializers.ValidationError({
                "supervisor.profilePhoto": ["Attach the actual image file, not only its metadata."],
            })
        return None
    try:
        validate_profile_image(photo)
    except serializers.ValidationError as exc:
        detail = exc.detail.get("image", exc.detail) if isinstance(exc.detail, dict) else exc.detail
        raise serializers.ValidationError({
            "supervisor.profilePhoto": detail if isinstance(detail, list) else [detail],
        })
    return photo


def register_supervisor(request, raw: dict) -> Response:
    """Save a supervisor's registration and answer with its receipt (see the
    module's notes): 201, or 200 for the same request sent again."""
    from .views import REGISTRATION_PER_IP_LIMIT, REGISTRATION_WINDOW_SECONDS, _client_ip

    parser = SupervisorIntakeInput(data=raw)
    if not parser.is_valid():
        errors = error_fields(parser.errors)
        raise serializers.ValidationError({key.removeprefix("payload."): value for key, value in errors.items()})
    require_policies(parser.validated_data)
    supervisor = parser.validated_data["payload"]["supervisor"]
    photo = _photo(request, supervisor)
    key_value = request.headers.get("Idempotency-Key")
    try:
        key = uuid.UUID(key_value) if key_value and len(key_value) <= 64 else None
    except (ValueError, AttributeError):
        key = None
    if key is None:
        raise serializers.ValidationError({"detail": "A valid UUID Idempotency-Key is required."})
    raw_token = request.headers.get("X-Registration-Invitation", "")
    actor = request.user if request.user.is_authenticated else None
    photo_digest = hashlib.sha256(photo.read()).hexdigest() if photo else None
    if photo:
        photo.seek(0)
    fingerprint = {
        "request": raw, "actor": getattr(actor, "pk", None), "invitation": token_hash(raw_token),
        "photo": photo_digest,
    }
    digest = token_hash(json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), allow_nan=False))
    previous = check_previous(key, digest)
    if previous:
        return Response(receipt(previous))
    rate_key = f"registration_ip:{_client_ip(request)}"
    attempts = cache.get(rate_key, 0)
    if attempts >= REGISTRATION_PER_IP_LIMIT:
        raise Throttled(wait=REGISTRATION_WINDOW_SECONDS)
    cache.set(rate_key, attempts + 1, REGISTRATION_WINDOW_SECONDS)
    created_file = None
    try:
        with transaction.atomic():
            window = current_window(lock=True)
            previous = check_previous(key, digest)
            if previous:
                return Response(receipt(previous))
            now = timezone.now()
            # Late links are a student's own: one given here is refused.
            valid_invitation(raw_token, window, now, journey=JOURNEY)
            if not window.is_open(now):
                raise serializers.ValidationError({"detail": "Registration is closed. Contact an administrator."})
            if User.objects.filter(email__iexact=supervisor["email"]).exists():
                raise _taken()
            user = save_supervisor(supervisor, now)
            User.objects.filter(pk=user.pk).update(policies_agreed_at=now)
            link_nominating_students(SupervisorProfile.objects.get(user=user), window, supervisor["relationship"])
            submission = RegistrationSubmission.objects.create(
                idempotency_key=key, request_digest=digest, window=window, student=user,
                student_count=0, journey=JOURNEY, created_by=actor, source={"method": JOURNEY},
                supervisor_mode=MODES[supervisor["relationship"]],
            )
            if photo:
                created_file = save_profile_image(user=user, uploaded_file=photo)
            # Its registration email, once it's saved (System Emails > Registration).
            from .registration_emails import send_registration_emails

            transaction.on_commit(lambda: send_registration_emails(JOURNEY, [user]))
            response = receipt(submission)
    except IntegrityError:
        if created_file:
            get_profile_image_storage().delete(created_file)
        previous = check_previous(key, digest)
        if previous:
            return Response(receipt(previous))
        if User.objects.filter(email__iexact=supervisor["email"]).exists():
            raise _taken()
        raise
    except Exception:
        if created_file:
            get_profile_image_storage().delete(created_file)
        raise
    return Response(response, status=201)
