"""A mentor registering on the public registration page (``journey:
"mentor"``): their contact details, affiliation, what they'd mentor, how many
groups and why, and when they're free each week.

Saved as the admin's Import Mentors saves a mentor: an account with the
mentor role, a mentor profile and their interests, with their weekly
availability. The account starts pending: it can't sign in until an admin
activates it on Admin > Mentors. As for students, the registration dates
apply (late links stay student only), an email with an account is refused
(but a mentor's back for a later year, which comes back pending: see
``apps.users.returning``), the same request sent again gets the same receipt
(its Idempotency-Key), and a registration email is sent once it's saved
(``registration_mentor``).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import Throttled
from rest_framework.response import Response

from apps.common.role_names import ROLE_MENTOR, get_role_by_name
from apps.resources.models import RoleAssignmentHistory

from .models import AreasOfInterest, MentorProfile, RegistrationSubmission, User, UserInterest
from .models.mentor_availability import MentorAvailability
from .registration_intake import (
    RegistrationWarnings, StrictInput, check_previous, current_window, error_fields, receipt, require_policies, resolve_location,
    token_hash,
    valid_invitation,
)
from .returning import returning_mentor
from .serializers import (
    MAILBOX_WHOSE, UNKNOWN_OVERRIDE, StrictBooleanField, mailbox_warning, name_email_warning, refuse_invalid_mailbox,
    refuse_placeholder, stored_email_answers,
)

JOURNEY = "mentor"
AFFILIATIONS = ("undergraduate", "postgraduate", "hdr", "academic", "industry")
# Students at university say which year they're in.
STUDYING = ("undergraduate", "postgraduate")
STUDY_YEARS = ("1", "2", "3", "4", "5+")
CAPACITIES = ("1", "2", "3", "4", "5")
# Their written answer (why they'd mentor), as the form counts it.
MAX_WORDS = 150
WRITTEN = ("motivation",)
SLOT_NOT_FULL = "Choose a day and both times."
MENTOR_OVERRIDES = {"ConfirmEmailInvalidOverride", "ConfirmNameEmailOverride"}
MENTOR_NAME = "the mentor's"


class AvailabilityInput(StrictInput):
    """One weekly time a mentor is free: Monday is "0", times "HH:MM". A row
    left empty is dropped."""

    weekday = serializers.CharField(max_length=1, allow_blank=True, default="")
    start = serializers.CharField(max_length=5, allow_blank=True, default="")
    end = serializers.CharField(max_length=5, allow_blank=True, default="")


class MentorInput(StrictInput):
    firstName = serializers.CharField(max_length=150)
    lastName = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    country = serializers.CharField(max_length=255)
    state = serializers.CharField(max_length=255, allow_blank=True, default="")
    affiliation = serializers.ChoiceField(choices=AFFILIATIONS)
    institution = serializers.CharField(max_length=255, allow_blank=True, default="")
    company = serializers.CharField(max_length=255, allow_blank=True, default="")
    universityYear = serializers.ChoiceField(choices=("", *STUDY_YEARS), default="")
    fieldOfStudy = serializers.CharField(max_length=255, allow_blank=True, default="")
    interests = serializers.ListField(child=serializers.CharField(max_length=255), max_length=100, default=list)
    capacity = serializers.ChoiceField(choices=CAPACITIES)
    motivation = serializers.CharField(max_length=5000)
    # Weekly times: the form no longer asks for them, but they're still taken
    # and kept when given.
    availability = serializers.ListField(child=AvailabilityInput(), max_length=21, default=list)
    overrides = serializers.DictField(child=StrictBooleanField(), default=dict)

    def validate_overrides(self, value):
        if set(value) - MENTOR_OVERRIDES:
            raise serializers.ValidationError(UNKNOWN_OVERRIDE)
        return value

    def validate_email(self, value):
        refuse_placeholder(value)
        return value

    def validate(self, data):
        errors = {}
        if data["country"].casefold() == "australia" and not data["state"]:
            errors["state"] = "Choose your state or territory."
        if data["affiliation"] == "industry":
            if not data["company"]:
                errors["company"] = "Enter your company or organisation."
        else:
            if not data["institution"]:
                errors["institution"] = "Enter your university or institution."
            if not data["fieldOfStudy"]:
                errors["fieldOfStudy"] = "Enter your field of study or research."
        if data["affiliation"] in STUDYING and not data["universityYear"]:
            errors["universityYear"] = "Enter your current year of study."
        if not data["interests"]:
            errors["interests"] = "Choose at least one area of expertise."
        for field in WRITTEN:
            if len(data[field].split()) > MAX_WORDS:
                errors[field] = f"Keep this to {MAX_WORDS} words or fewer."
        slots = []
        for index, slot in enumerate(data["availability"]):
            given = [slot["weekday"], slot["start"], slot["end"]]
            if not any(given):
                continue
            if not all(given):
                errors[f"availability.{index}"] = SLOT_NOT_FULL
                continue
            try:
                weekday = int(slot["weekday"])
                start = datetime.strptime(slot["start"], "%H:%M").time()
                end = datetime.strptime(slot["end"], "%H:%M").time()
            except ValueError:
                errors[f"availability.{index}"] = SLOT_NOT_FULL
                continue
            if not 0 <= weekday <= 6:
                errors[f"availability.{index}"] = SLOT_NOT_FULL
            elif end <= start:
                errors[f"availability.{index}"] = "End after it starts."
            elif (weekday, start, end) not in slots:
                slots.append((weekday, start, end))
        if errors:
            raise serializers.ValidationError(errors)
        data["availability"] = slots
        data["email"] = data["email"].lower()
        return data


class MentorPayloadInput(StrictInput):
    mentor = MentorInput()


class MentorIntakeInput(StrictInput):
    journey = serializers.ChoiceField(choices=[JOURNEY])
    payload = MentorPayloadInput()
    # The BIOTech Futures policies, ticked on the form's last step: needed.
    policiesAgreed = serializers.BooleanField(required=False, default=False)


def save_mentor(mentor: dict, now, *, returning: User | None = None) -> User:
    """The mentor's account, pending until an admin activates it, with the
    mentor role, profile, interests and weekly availability. A mentor back
    for a later year (``returning``, apps.users.returning) gets their account
    back, pending again, with this form's details in place of last year's."""
    country, state = resolve_location(mentor)
    industry = mentor["affiliation"] == "industry"
    details = {
        "background": mentor["affiliation"],
        "institution": "" if industry else mentor["institution"],
        "company": mentor["company"] if industry else "",
        "university_year": mentor["universityYear"] if mentor["affiliation"] in STUDYING else "",
        "field_of_study": "" if industry else mentor["fieldOfStudy"],
        "mentor_reason": mentor["motivation"],
        "max_group_count": int(mentor["capacity"]),
    }
    mentor_role = get_role_by_name(ROLE_MENTOR)
    if returning is None:
        user = User.objects.create_user(
            email=mentor["email"], first_name=mentor["firstName"], last_name=mentor["lastName"],
            country=country, state=state,
        )
        RoleAssignmentHistory.objects.create(user=user, role=mentor_role, valid_from=now, valid_to=None)
        MentorProfile.objects.create(user=user, **details)
    else:
        user = returning
        user.first_name, user.last_name = mentor["firstName"], mentor["lastName"]
        user.country, user.state = country, state
        user.mark_pending(save=False)
        user.save()
        # Their mentor role, unless they still hold it.
        if not RoleAssignmentHistory.objects.filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now), user=user, role=mentor_role,
        ).exists():
            RoleAssignmentHistory.objects.create(user=user, role=mentor_role, valid_from=now, valid_to=None)
        MentorProfile.objects.filter(user=user).update(**details)
        UserInterest.objects.filter(user=user).delete()
        MentorAvailability.objects.filter(mentor_user=user).delete()
    for description in dict.fromkeys(mentor["interests"]):
        interest, _ = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description, defaults={"interest_desc": description},
        )
        UserInterest.objects.get_or_create(user=user, interest=interest)
    MentorAvailability.objects.bulk_create([
        MentorAvailability(mentor_user=user, weekday=weekday, start_time=start, end_time=end)
        for weekday, start, end in mentor["availability"]
    ])
    return user


MENTOR_EMAIL_TAKEN = "An account with this email already exists."


def mentor_email_taken(email, window) -> bool:
    """Whether ``email`` has an account, other than a mentor's back for a later year."""
    return returning_mentor(email, window) is None and User.objects.filter(email__iexact=email).exists()


def _taken() -> serializers.ValidationError:
    return serializers.ValidationError({"mentor.email": [MENTOR_EMAIL_TAKEN]})


def mentor_warnings(mentor: dict, answers) -> list[dict]:
    """A mentor's soft warnings, as a student's (registration_warnings): the
    name-and-email mismatch and an unknown mailbox, unless confirmed."""
    warnings = [
        name_email_warning(mentor["firstName"], mentor["lastName"], mentor["email"], MENTOR_NAME),
        mailbox_warning(answers, mentor["email"], "Title", invalid_is_error=True),
    ]
    return [
        {**warning, "field": "mentor.email", "override_field": f"mentor.overrides.{warning['override_field']}"}
        for warning in warnings if warning and not mentor["overrides"].get(warning["override_field"])
    ]


def register_mentor(request, raw: dict) -> Response:
    """Save a mentor's registration and answer with its receipt (see the
    module's notes): 201, or 200 for the same request sent again."""
    from .views import REGISTRATION_PER_IP_LIMIT, REGISTRATION_WINDOW_SECONDS, _client_ip

    parser = MentorIntakeInput(data=raw)
    if not parser.is_valid():
        errors = error_fields(parser.errors)
        raise serializers.ValidationError({key.removeprefix("payload."): value for key, value in errors.items()})
    require_policies(parser.validated_data)
    mentor = parser.validated_data["payload"]["mentor"]
    if request.FILES:
        raise serializers.ValidationError({"detail": "A mentor's registration has no files."})
    key_value = request.headers.get("Idempotency-Key")
    try:
        key = uuid.UUID(key_value) if key_value and len(key_value) <= 64 else None
    except (ValueError, AttributeError):
        key = None
    if key is None:
        raise serializers.ValidationError({"detail": "A valid UUID Idempotency-Key is required."})
    raw_token = request.headers.get("X-Registration-Invitation", "")
    actor = request.user if request.user.is_authenticated else None
    fingerprint = {"request": raw, "actor": getattr(actor, "pk", None), "invitation": token_hash(raw_token)}
    digest = token_hash(json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), allow_nan=False))
    previous = check_previous(key, digest)
    if previous:
        return Response(receipt(previous))
    rate_key = f"registration_ip:{_client_ip(request)}"
    attempts = cache.get(rate_key, 0)
    if attempts >= REGISTRATION_PER_IP_LIMIT:
        raise Throttled(wait=REGISTRATION_WINDOW_SECONDS)
    cache.set(rate_key, attempts + 1, REGISTRATION_WINDOW_SECONDS)
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
            if mentor_email_taken(mentor["email"], window):
                raise _taken()
            answers = stored_email_answers([mentor["email"]])
            try:
                refuse_invalid_mailbox(answers, mentor["email"], MAILBOX_WHOSE["Title"])
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"mentor.email": error.detail})
            warnings = mentor_warnings(mentor, answers)
            if warnings:
                raise RegistrationWarnings(warnings)
            returning = returning_mentor(mentor["email"], window)
            user = save_mentor(mentor, now, returning=returning)
            User.objects.filter(pk=user.pk).update(policies_agreed_at=now)
            submission = RegistrationSubmission.objects.create(
                idempotency_key=key, request_digest=digest, window=window, student=user,
                student_count=0, journey=JOURNEY, created_by=actor, source={"method": JOURNEY},
            )
            # Its registration email, once it's saved (System Emails > Registration).
            from .registration_emails import send_registration_emails

            transaction.on_commit(lambda: send_registration_emails(JOURNEY, [user]))
            response = receipt(submission)
    except IntegrityError:
        previous = check_previous(key, digest)
        if previous:
            return Response(receipt(previous))
        if User.objects.filter(email__iexact=mentor["email"]).exists():
            raise _taken()
        raise
    return Response(response, status=201)
