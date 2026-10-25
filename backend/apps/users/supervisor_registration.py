"""A supervisor (a teacher, usually) registering on the public registration
page (``journey: "supervisor"``): their contact details, their school, whether
they're a teacher or a parent and where they are. Pronouns and a profile photo
are still accepted, though the page no longer asks for them.

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
from django.db.models import Q
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
from .returning import returning_self_supervisor
from .registration_intake import (
    PhotoMetadataInput, RegistrationWarnings, StrictInput, check_previous, current_window, error_fields, receipt,
    require_policies, resolve_location, token_hash,
    valid_invitation,
)
from .serializers import (
    MAILBOX_WHOSE, UNKNOWN_OVERRIDE, StrictBooleanField, mailbox_warning, name_email_warning,
    refuse_invalid_mailbox, refuse_placeholder, stored_email_answers,
)

JOURNEY = "supervisor"
# A supervisor's email is checked as a mentor's is: an address that doesn't
# exist is refused; one that couldn't be checked, or that looks like a typo of
# their name, is a warning they confirm (overrides).
SUPERVISOR_OVERRIDES = {"ConfirmEmailInvalidOverride", "ConfirmNameEmailOverride"}
SUPERVISOR_NAME = "the supervisor's"
SUPERVISOR_EMAIL_TAKEN = "An account with this email already exists."
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
    overrides = serializers.DictField(child=StrictBooleanField(), default=dict)

    def validate_overrides(self, value):
        if set(value) - SUPERVISOR_OVERRIDES:
            raise serializers.ValidationError(UNKNOWN_OVERRIDE)
        return value

    def validate_email(self, value):
        refuse_placeholder(value)
        return value

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


def save_supervisor(supervisor: dict, now, *, returning: User | None = None) -> User:
    """The supervisor's account, active at once, with the supervisor role and
    profile (their school). A supervisor back for a later year (``returning``,
    deactivated by Start new year) gets their account back, active again,
    with this form's details in place of last year's, as a mentor does."""
    country, state = resolve_location(supervisor)
    pronouns = supervisor["pronounsOther"] if supervisor["pronouns"] == "Other" else supervisor["pronouns"]
    role = get_role_by_name(ROLE_SUPERVISOR)
    if returning is None:
        user = User.objects.create_user(
            email=supervisor["email"], first_name=supervisor["firstName"], last_name=supervisor["lastName"],
            country=country, state=state, pronouns=pronouns,
            account_status=User.AccountStatus.ACTIVE, is_active=True, activated_at=now,
        )
        RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now, valid_to=None)
        SupervisorProfile.objects.create(user=user, school_name=supervisor["school"])
        return user
    user = returning
    user.first_name, user.last_name = supervisor["firstName"], supervisor["lastName"]
    user.country, user.state = country, state
    # The form no longer asks for pronouns: theirs stay unless some are sent.
    user.pronouns = pronouns or user.pronouns
    user.activate(save=False)
    user.save()
    # Their supervisor role, unless they still hold it.
    if not RoleAssignmentHistory.objects.filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now), user=user, role=role,
    ).exists():
        RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now, valid_to=None)
    SupervisorProfile.objects.update_or_create(user=user, defaults={"school_name": supervisor["school"]})
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


def supervisor_email_taken(email) -> bool:
    """Whether ``email`` has an account, other than a supervisor's back for a
    later year (returning_self_supervisor), whose details are updated."""
    return returning_self_supervisor(email) is None and User.objects.filter(email__iexact=email).exists()


def _taken() -> serializers.ValidationError:
    return serializers.ValidationError({"supervisor.email": [SUPERVISOR_EMAIL_TAKEN]})


def supervisor_warnings(supervisor: dict, answers) -> list[dict]:
    """A supervisor's soft warnings, as a mentor's (mentor_warnings): the
    name-and-email mismatch and an unknown mailbox, unless confirmed."""
    warnings = [
        name_email_warning(supervisor["firstName"], supervisor["lastName"], supervisor["email"], SUPERVISOR_NAME),
        mailbox_warning(answers, supervisor["email"], "Title", invalid_is_error=True),
    ]
    return [
        {**warning, "field": "supervisor.email", "override_field": f"supervisor.overrides.{warning['override_field']}"}
        for warning in warnings if warning and not supervisor["overrides"].get(warning["override_field"])
    ]


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
            if supervisor_email_taken(supervisor["email"]):
                raise _taken()
            answers = stored_email_answers([supervisor["email"]])
            try:
                refuse_invalid_mailbox(answers, supervisor["email"], MAILBOX_WHOSE["Title"])
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"supervisor.email": error.detail})
            warnings = supervisor_warnings(supervisor, answers)
            if warnings:
                raise RegistrationWarnings(warnings)
            user = save_supervisor(supervisor, now, returning=returning_self_supervisor(supervisor["email"]))
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
