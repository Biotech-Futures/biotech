"""A mentor registering on the public registration page (``journey:
"mentor"``): their contact details, affiliation, what they'd mentor and how,
and when they're free each week.

Saved as the admin's Import Mentors saves a mentor: an account with the
mentor role, a mentor profile and their interests, with their weekly
availability. The account starts pending: it can't sign in until an admin
activates it on Admin > Mentors. As for students, the registration dates
apply (late links stay student only), an email with an account is refused,
the same request sent again gets the same receipt (its Idempotency-Key), and
a registration email is sent once it's saved (``registration_mentor``).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import Throttled
from rest_framework.response import Response

from apps.common.role_names import ROLE_MENTOR, get_role_by_name
from apps.resources.models import RoleAssignmentHistory

from .models import AreasOfInterest, MentorProfile, RegistrationSubmission, User, UserInterest
from .models.mentor_availability import MentorAvailability
from .registration_intake import (
    StrictInput, check_previous, current_window, error_fields, receipt, require_policies, resolve_location,
    token_hash,
    valid_invitation,
)

JOURNEY = "mentor"
AFFILIATIONS = ("undergraduate", "postgraduate", "hdr", "academic", "industry")
# Students at university say which year they're in.
STUDYING = ("undergraduate", "postgraduate")
STUDY_YEARS = ("1", "2", "3", "4", "5+")
CAPACITIES = ("1", "2", "3", "4", "5")
# Hours a week they can give, as a whole number.
MAX_WEEKLY_HOURS = 40
# Each written answer, as the form counts it.
MAX_WORDS = 150
WRITTEN = ("background", "motivation", "mentoringApproach")
SLOT_NOT_FULL = "Choose a day and both times."


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
    weeklyHours = serializers.IntegerField(min_value=1, max_value=MAX_WEEKLY_HOURS)
    background = serializers.CharField(max_length=5000)
    motivation = serializers.CharField(max_length=5000)
    mentoringApproach = serializers.CharField(max_length=5000)
    # Weekly times: the form no longer asks for them, but they're still taken
    # and kept when given.
    availability = serializers.ListField(child=AvailabilityInput(), max_length=21, default=list)

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
            errors["interests"] = "Choose at least one relevant interest."
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


def save_mentor(mentor: dict, now) -> User:
    """The mentor's account, pending until an admin activates it, with the
    mentor role, profile, interests and weekly availability."""
    country, state = resolve_location(mentor)
    user = User.objects.create_user(
        email=mentor["email"], first_name=mentor["firstName"], last_name=mentor["lastName"],
        country=country, state=state,
    )
    RoleAssignmentHistory.objects.create(user=user, role=get_role_by_name(ROLE_MENTOR), valid_from=now, valid_to=None)
    industry = mentor["affiliation"] == "industry"
    MentorProfile.objects.create(
        user=user,
        background=mentor["affiliation"],
        institution="" if industry else mentor["institution"],
        company=mentor["company"] if industry else "",
        university_year=mentor["universityYear"] if mentor["affiliation"] in STUDYING else "",
        field_of_study="" if industry else mentor["fieldOfStudy"],
        mentor_reason=mentor["motivation"],
        max_group_count=int(mentor["capacity"]),
        weekly_hours=mentor["weeklyHours"],
        relevant_background=mentor["background"],
        mentoring_approach=mentor["mentoringApproach"],
    )
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


def _taken() -> serializers.ValidationError:
    return serializers.ValidationError({"mentor.email": ["An account with this email already exists."]})


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
            if User.objects.filter(email__iexact=mentor["email"]).exists():
                raise _taken()
            user = save_mentor(mentor, now)
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
