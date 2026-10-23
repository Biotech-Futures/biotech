from rest_framework import serializers
from .models import (
    User,
    StudentProfile,
    MentorProfile,
    SupervisorProfile,
    UserInterest,
    AreasOfInterest,
    KnownUniversity,
    EmailVerification,
)
from apps.groups.models import Countries, CountryStates
from apps.resources.models import RoleAssignmentHistory
from apps.common.role_names import ROLE_MENTOR, ROLE_STUDENT, ROLE_SUPERVISOR
from django.db import DatabaseError
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from zoneinfo import available_timezones


# What the form's ``RegisteredBy`` says when someone else registered the
# student (the same answers UserRegisterView reads as peer, supervisor or
# admin). Their guardian can be added later. A student registering
# individually, or a form that doesn't say who filled it in, has to name one.
_GUARDIAN_OPTIONAL_FOR = {"peer", "team", "supervisor", "teacher", "admin"}
GUARDIAN_FIELDS = ("GuardianName", "GuardianSurname", "GuardianEmail")
GUARDIAN_TOGETHER = "Enter the guardian's first name, surname and email together."
PLACEHOLDER_EMAIL = "This is a placeholder address from the template: replace it or exclude the row."


def is_placeholder_email(address) -> bool:
    """An address on the reserved .invalid domain, as the CSV template's example row uses."""
    domain = str(address or "").strip().lower().rpartition("@")[2].rstrip(".")
    return domain == "invalid" or domain.endswith(".invalid")


def refuse_placeholder(value):
    if is_placeholder_email(value):
        raise serializers.ValidationError(PLACEHOLDER_EMAIL, code="placeholder_email")
REGISTRATION_OVERRIDES = {
    "ConfirmSchoolOverride", "ConfirmNameEmailOverride",
    "ConfirmEmailInvalidOverride", "ConfirmGuardianEmailInvalidOverride",
    "ConfirmSupervisorEmailInvalidOverride", "ConfirmGuardianEmailHasAccountOverride",
}
GUARDIAN_IS_STUDENT = "This email address belongs to a student account, so it can't be used as a guardian's email."
GUARDIAN_IS_SELF = "The guardian cannot be the same person as the student."
SUPERVISOR_IS_SELF = "The supervisor cannot be the same person as the student."
GUARDIAN_HAS_ACCOUNT = "This email address already has an account. Please confirm it is the guardian's own address."
MAILBOX_WHOSE = {
    "Title": "This email address",
    "GuardianEmail": "The guardian's email address",
    "SupervisorEmail": "The supervisor's email address",
}


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid", input=data)
        return data


def _edit_distance(a, b):
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        current = [i + 1]
        for j, cb in enumerate(b):
            current.append(min(current[j] + 1, previous[j + 1] + 1, previous[j] + (ca != cb)))
        previous = current
    return previous[-1]


def email_precheck_enabled() -> bool:
    return bool(getattr(settings, "EMAIL_PRECHECK_ENABLED", False))


def stored_email_answers(addresses) -> dict:
    """The fresh QuickEmailVerification answers on file for ``addresses``
    (see EmailVerification.reusable), keyed by lower-case address: one query for a whole
    submission, read whether or not EMAIL_PRECHECK_ENABLED is on. Any failure gives
    no answers, so registration goes on unchecked."""
    try:
        return EmailVerification.reusable(
            addresses, max_age_days=int(getattr(settings, "QEV_RESULT_MAX_AGE_DAYS", 180)),
        )
    except DatabaseError:
        return {}


def refuse_invalid_mailbox(answers, address, whose):
    """Refuse ``address`` when its answer in ``answers`` (anything with ``get``)
    says it doesn't exist."""
    answer = answers.get((address or "").strip().lower())
    if answer is None or answer.status != EmailVerification.Status.INVALID:
        return
    suggestion = f" Did you mean {answer.did_you_mean}?" if answer.did_you_mean else ""
    raise serializers.ValidationError(
        f"{whose} doesn't appear to exist.{suggestion} Please correct it.", code="email_invalid_address",
    )


def _invalid_email_warning(answers, address, *, code, field, override, whose, invalid_is_error=False):
    """A warning when ``address``'s answer on file says it doesn't exist, or
    that it couldn't be told (unknown). With ``invalid_is_error`` a doesn't-exist
    answer is a hard error instead (UserRegisterBodySerializer), so no warning."""
    answer = answers.get((address or "").strip().lower())
    if answer is None:
        return None
    if answer.status == EmailVerification.Status.INVALID and not invalid_is_error:
        suggestion = f" Did you mean {answer.did_you_mean}?" if answer.did_you_mean else ""
        message = f"{whose} doesn't appear to exist.{suggestion} Please correct it, or confirm if this is correct."
    elif answer.status == EmailVerification.Status.UNKNOWN:
        message = f"{whose} couldn't be verified. Please check it, or confirm if this is correct."
    else:
        return None
    return {"code": code, "field": field, "override_field": override, "message": message}


def registration_warnings(
    data, email_answers=None, known_schools=None, *, check_supervisor=False, invalid_is_error=False,
    guardian_accounts=None,
):
    """The soft warnings for one student's registration details, each with
    the override that confirms past it. ``email_answers`` is
    ``stored_email_answers`` for the submission: an address answered invalid
    or unknown gets a warning, and one with no answer gets none (it isn't blocked).
    ``check_supervisor`` adds the supervisor the student named (once, on the
    first student; never a supervisor registering their own students).
    ``known_schools`` is ``KnownUniversity.matching`` for the submission's
    school names; without it, this student's is looked up on its own.
    ``invalid_is_error``: a doesn't-exist answer is a hard error, so only
    unknown warns. ``guardian_accounts``: the submission's guardian addresses
    that have an account; without it, this student's is looked up on its own."""
    warnings = []
    school = data.get("SchoolName", "").strip().lower()
    known = (
        KnownUniversity.normalise(school).lower() in known_schools if known_schools is not None
        else KnownUniversity.matches(school)
    )
    if ("university" in school or known) and not data.get("ConfirmSchoolOverride"):
        warnings.append({
            "code": "university_school",
            "field": "SchoolName",
            "override_field": "ConfirmSchoolOverride",
            "message": "This looks like a university, not a school. Please confirm if this is correct.",
        })
    name = (data.get("FirstName", "").strip() + data.get("Surname", "").strip()).lower().replace(" ", "")
    local = data.get("Title", "").strip().lower().split("@")[0].replace(".", "").replace("_", "")
    if 1 <= _edit_distance(name, local) <= 2 and not data.get("ConfirmNameEmailOverride"):
        warnings.append({
            "code": "name_email_mismatch",
            "field": "Title",
            "override_field": "ConfirmNameEmailOverride",
            "message": "This email looks like it might have a typo compared to the student's name. Please confirm.",
        })
    guardian_email = data.get("GuardianEmail", "").strip().lower()
    if guardian_email and not data.get("ConfirmGuardianEmailHasAccountOverride"):
        # A current student's address is refused before this (validate_GuardianEmail).
        has_account = (
            guardian_email in guardian_accounts if guardian_accounts is not None
            else User.objects.filter(email__iexact=guardian_email).exists()
        )
        if has_account:
            warnings.append({
                "code": "guardian_email_has_account",
                "field": "GuardianEmail",
                "override_field": "ConfirmGuardianEmailHasAccountOverride",
                "message": GUARDIAN_HAS_ACCOUNT,
            })
    if email_answers:
        for warning, confirmed in (
            (_invalid_email_warning(
                email_answers, data.get("Title"), code="email_invalid", field="Title",
                override="ConfirmEmailInvalidOverride", whose="This email address", invalid_is_error=invalid_is_error,
            ), data.get("ConfirmEmailInvalidOverride")),
            (_invalid_email_warning(
                email_answers, data.get("GuardianEmail"), code="guardian_email_invalid", field="GuardianEmail",
                override="ConfirmGuardianEmailInvalidOverride", whose="The guardian's email address",
                invalid_is_error=invalid_is_error,
            ), data.get("ConfirmGuardianEmailInvalidOverride")),
            (check_supervisor and _invalid_email_warning(
                email_answers, data.get("SupervisorEmail"), code="supervisor_email_invalid",
                field="SupervisorEmail", override="ConfirmSupervisorEmailInvalidOverride",
                whose="The supervisor's email address", invalid_is_error=invalid_is_error,
            ), data.get("ConfirmSupervisorEmailInvalidOverride")),
        ):
            if warning and not confirmed:
                warnings.append(warning)
    return warnings


def _has_role(user, profile_model, role_name) -> bool:
    """Whether the account is a student or supervisor: it has that profile, or
    has ever been given that role."""
    return (
        profile_model.objects.filter(user=user).exists()
        or RoleAssignmentHistory.objects.filter(user=user, role__role_name__iexact=role_name).exists()
    )


# Validate body payload
class UserRegisterBodySerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("allow_partial_student"):
            for field in ("Country", "SchoolName", "YearLevel"):
                self.fields[field].allow_blank = True

    Title = serializers.EmailField(max_length=254)
    FirstName = serializers.CharField(max_length=255)
    Surname = serializers.CharField(max_length=255)
    Country = serializers.CharField(max_length=255)
    Region = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # A nominated supervisor is optional (a supervisor registering is one).
    SupervisorEmail = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    SupervisorFirstName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    SupervisorSurname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # Required unless a peer or supervisor is registering the student; see validate().
    GuardianEmail = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    GuardianName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    GuardianSurname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    SchoolName = serializers.CharField(max_length=255)
    YearLevel = serializers.ChoiceField(choices=["9", "10", "11", "12"])
    # A student's Areas of Interest are optional.
    Areaofinterest = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # Who filled the form in: "Self", "Peer" or "Supervisor". A supervisor's
    # registration locks the student's own details; missing leaves them editable.
    RegisteredBy = serializers.CharField(max_length=32, required=False, allow_blank=True)
    ConfirmSchoolOverride = StrictBooleanField(required=False, default=False)
    ConfirmNameEmailOverride = StrictBooleanField(required=False, default=False)
    # Confirm an address QuickEmailVerification answered as not existing.
    ConfirmEmailInvalidOverride = StrictBooleanField(required=False, default=False)
    ConfirmGuardianEmailInvalidOverride = StrictBooleanField(required=False, default=False)
    ConfirmSupervisorEmailInvalidOverride = StrictBooleanField(required=False, default=False)
    # Confirm a guardian address that already has a (non-student) account.
    ConfirmGuardianEmailHasAccountOverride = StrictBooleanField(required=False, default=False)

    def _refuse_invalid_mailbox(self, value, field):
        answers = self.context.get("email_answers")
        if answers and self.context.get("invalid_is_error"):
            refuse_invalid_mailbox(answers, value, MAILBOX_WHOSE[field])

    def validate_Title(self, value):
        # `Title` is the student's own email (mislabeled field name; confirmed
        # against the real Qualtrics form). Block registration if this email
        # is already in use, but by a student back for a later year, whose
        # account registering brings back (apps.users.returning).
        refuse_placeholder(value)
        from .returning import returning_student

        existing = User.objects.filter(email__iexact=value).first()
        if existing is not None:
            if _has_role(existing, SupervisorProfile, ROLE_SUPERVISOR):
                raise serializers.ValidationError(
                    "This email address already belongs to a supervisor, so it "
                    "cannot be used to register a student.",
                    code="student_email_is_supervisor",
                )
            if returning_student(value) is None:
                raise serializers.ValidationError(
                    "An account with this email address already exists.",
                    code="email_taken",
                )
        self._refuse_invalid_mailbox(value, "Title")
        return value

    def validate_GuardianEmail(self, value):
        refuse_placeholder(value)
        if not value:
            return value
        from .returning import returning_student

        existing = User.objects.filter(email__iexact=value).first()
        if (
            existing is not None and _has_role(existing, StudentProfile, ROLE_STUDENT)
            and returning_student(value) is None
        ):
            raise serializers.ValidationError(GUARDIAN_IS_STUDENT, code="guardian_email_is_student")
        self._refuse_invalid_mailbox(value, "GuardianEmail")
        return value

    def validate_SupervisorEmail(self, value):
        # A nominated supervisor is either new or already a supervisor. Any
        # other existing account is refused, so the form can't hand someone
        # else's account the supervisor role.
        refuse_placeholder(value)
        if not value:
            return value
        existing = User.objects.filter(email__iexact=value).first()
        if existing is not None:
            if _has_role(existing, StudentProfile, ROLE_STUDENT):
                raise serializers.ValidationError(
                    "This email address belongs to a student, so they cannot be "
                    "nominated as a supervisor.",
                    code="supervisor_email_is_student",
                )
            if not _has_role(existing, SupervisorProfile, ROLE_SUPERVISOR):
                raise serializers.ValidationError(
                    "This email address belongs to an existing account that is "
                    "not a supervisor.",
                    code="supervisor_email_in_use",
                )
        # Only a supervisor the student typed, never a signed-in one.
        if self.context.get("check_supervisor"):
            self._refuse_invalid_mailbox(value, "SupervisorEmail")
        return value

    def validate(self, data):
        student_email = data.get("Title", "").strip().lower()
        student_first = data.get("FirstName", "").strip().lower()
        student_last = data.get("Surname", "").strip().lower()

        guardian_email = data.get("GuardianEmail", "").strip().lower()
        guardian_first = data.get("GuardianName", "").strip().lower()
        guardian_last = data.get("GuardianSurname", "").strip().lower()

        supervisor_email = data.get("SupervisorEmail", "").strip().lower()
        supervisor_first = data.get("SupervisorFirstName", "").strip().lower()
        supervisor_last = data.get("SupervisorSurname", "").strip().lower()

        # Guardian details are required unless the student is being
        # registered by a peer or their supervisor.
        registered_by = data.get("RegisteredBy", "").strip().lower()
        if registered_by not in _GUARDIAN_OPTIONAL_FOR:
            missing = {
                field: serializers.ValidationError(
                    "This field is required when a student registers individually.",
                    code="guardian_required",
                ).detail
                for field in ("GuardianEmail", "GuardianName", "GuardianSurname")
                if not data.get(field, "").strip()
            }
            if missing:
                raise serializers.ValidationError(missing)
        given = [field for field in GUARDIAN_FIELDS if data.get(field, "").strip()]
        if given and len(given) < len(GUARDIAN_FIELDS):
            raise serializers.ValidationError({
                field: serializers.ValidationError(GUARDIAN_TOGETHER, code="guardian_incomplete").detail
                for field in GUARDIAN_FIELDS if field not in given
            })

        # Guardian can't be the same person as the student. Blank guardian
        # details match no one.
        if (guardian_email and student_email == guardian_email) or (
            guardian_first and guardian_last
            and student_first == guardian_first and student_last == guardian_last
        ):
            error = serializers.ValidationError(GUARDIAN_IS_SELF, code="guardian_same_as_student").detail
            raise serializers.ValidationError(
                {"GuardianEmail": error} if self.context.get("canonical_registration_fields") else error
            )

        # Supervisor can't be the same person as the student. Blank supervisor
        # details (none nominated) match no one.
        if (supervisor_email and student_email == supervisor_email) or (
            supervisor_first and supervisor_last
            and student_first == supervisor_first and student_last == supervisor_last
        ):
            error = serializers.ValidationError(SUPERVISOR_IS_SELF, code="supervisor_same_as_student").detail
            raise serializers.ValidationError(
                {"SupervisorEmail": error} if self.context.get("canonical_registration_fields") else error
            )

        if not self.context.get("defer_warnings"):
            warnings = registration_warnings(data)
            if warnings:
                raise serializers.ValidationError(warnings[0]["message"])

        return data

# Registration Wrapper
class UserRegisterRequestSerializer(serializers.Serializer):
    body = UserRegisterBodySerializer()

# Validate join permission
class JoinPermissionBodySerializer(serializers.Serializer):
    Email = serializers.EmailField()
    ResponseID = serializers.CharField(max_length=255)

# Join Permission Wrapper
class JoinPermissionRequestSerializer(serializers.Serializer):
    body = JoinPermissionBodySerializer()


class SelfNameSerializer(serializers.Serializer):
    """The name and pronouns a supervisor may change on their own profile."""

    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    # Blank leaves them unsaid.
    pronouns = serializers.CharField(max_length=100, required=False, allow_blank=True)


class StudentSelfProfileUpdateSerializer(serializers.Serializer):
    """Fields a student may update only when no supervisor manages them."""

    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    # Blank leaves them unsaid, as registering allows.
    pronouns = serializers.CharField(max_length=100, required=False, allow_blank=True)
    school_name = serializers.CharField(max_length=255, required=False)
    year_lvl = serializers.ChoiceField(
        choices=[str(level) for level in range(9, 13)],
        required=False,
    )
    pg_firstname = serializers.CharField(max_length=255, required=False)
    pg_lastname = serializers.CharField(max_length=255, required=False)
    pg_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    country_id = serializers.PrimaryKeyRelatedField(queryset=Countries.objects.all(), required=False, allow_null=True)
    state_id = serializers.PrimaryKeyRelatedField(queryset=CountryStates.objects.all(), required=False, allow_null=True)
    interest_ids = serializers.PrimaryKeyRelatedField(queryset=AreasOfInterest.objects.all(), many=True, required=False)

class UserSerializer(serializers.ModelSerializer):
    current_role_id = serializers.SerializerMethodField()
    current_role_name = serializers.SerializerMethodField()

    #student
    pg_firstname = serializers.SerializerMethodField()
    pg_lastname = serializers.SerializerMethodField()
    pg_email = serializers.SerializerMethodField()
    year_lvl = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    join_perm = serializers.SerializerMethodField()
    joinperm_granted_at = serializers.SerializerMethodField()
    join_perm_granted_at = serializers.SerializerMethodField()
    pending_guardian = serializers.SerializerMethodField()

    #mentor
    ment_inst = serializers.SerializerMethodField()
    ment_reason = serializers.SerializerMethodField()
    ment_max_groups = serializers.SerializerMethodField()
    # Their details as their admin panel shows them, for their own profile.
    mentor_details = serializers.SerializerMethodField()

    # Profile page additions (read-only):
    #   * `interests` is the user's selected areas of interest (any role).
    #   * `supervisor_name` / `supervisor_email` are populated for students,
    #     resolved via StudentProfile.supervisor -> SupervisorProfile.user.
    #   * `supervisor_school_name` is populated for users currently holding the
    #     supervisor role, pulled from their SupervisorProfile.
    interests = serializers.SerializerMethodField()
    supervisor_name = serializers.SerializerMethodField()
    supervisor_email = serializers.SerializerMethodField()
    supervisor_school_name = serializers.SerializerMethodField()
    supervised_students = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    guardian_reminder = serializers.SerializerMethodField()
    supervisor_id = serializers.SerializerMethodField()
    # The student's own details are their supervisor's to change (see StudentProfile.details_locked).
    details_locked = serializers.SerializerMethodField()
    # Their guardian too, once permission is given (see StudentProfile.guardian_locked).
    guardian_locked = serializers.SerializerMethodField()

    # Onboarding gate: tells the FE whether the user is still on their
    # invited/default-password state and must complete the password set/change
    # flow before they're allowed into the dashboard. See `get_must_change_password`.
    must_change_password = serializers.SerializerMethodField()

    # Geography for matching + profile display. Read-only nested shapes; writes go
    # through the admin user service (countryId/stateId). Country is the field that
    # matters — state is sub-national and often blank.
    country = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "account_status",
            "country",
            "state",
            "current_role_id",
            "current_role_name",
            "pg_firstname",
            "pg_lastname",
            "pg_email",
            "year_lvl",
            "school_name",
            "join_perm",
            "joinperm_granted_at",
            "join_perm_granted_at",
            "pending_guardian",
            "ment_inst",
            "ment_reason",
            "ment_max_groups",
            "mentor_details",
            "interests",
            "supervisor_name",
            "supervisor_email",
            "supervisor_school_name",
            "supervised_students",
            "profile_image_url",
            "guardian_reminder",
            "supervisor_id",
            "details_locked",
            "guardian_locked",
            "must_change_password",
            "timezone",
            "pronouns",
        ]
        read_only_fields = [
            "id",
            "pronouns",
            "interests",
            "supervisor_name",
            "supervisor_email",
            "supervisor_school_name",
            "supervised_students",
            "profile_image_url",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance cache so serializing one user doesn't fire 10+ queries
        # for the same RoleAssignmentHistory / StudentProfile / MentorProfile.
        self._cache_assignment: dict[int, object] = {}
        self._cache_student: dict[int, object] = {}
        self._cache_mentor: dict[int, object] = {}
        self._cache_supervisor: dict[int, object] = {}
        self._cache_interests: dict[int, list[str]] = {}

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_country(self, obj):
        if not obj.country_id:
            return None
        return {"id": obj.country.id, "countryName": obj.country.country_name}

    def get_supervisor_id(self, obj):
        profile = self._student_profile(obj)
        return profile.supervisor_id if profile else None

    def get_details_locked(self, obj):
        profile = self._student_profile(obj)
        return bool(profile and profile.details_locked)

    def get_guardian_locked(self, obj):
        profile = self._student_profile(obj)
        return bool(profile and profile.guardian_locked)

    def get_guardian_reminder(self, obj):
        from .guardian_reminders import reminder_info
        profile = self._student_profile(obj)
        return reminder_info(profile) if profile else None

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_state(self, obj):
        if not obj.state_id:
            return None
        # No countryName here — `country` is the single source of truth for that.
        return {
            "id": obj.state.id,
            "stateName": obj.state.state_name,
        }

    def validate_timezone(self, value):
        if value not in available_timezones():
            raise serializers.ValidationError(f"Unknown IANA timezone: {value!r}")
        return value

    def _active_assignment(self, user):
        if user.id in self._cache_assignment:
            return self._cache_assignment[user.id]
        now = timezone.now()
        rah = (
            RoleAssignmentHistory.objects
            .select_related("role")
            .filter(user=user, valid_from__lte=now)
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
            .order_by("-valid_from")
            .first()
        )
        self._cache_assignment[user.id] = rah
        return rah

    @staticmethod
    def _is_role(rah, expected_name: str) -> bool:
        # Identify the active role by canonical name instead of PK. ``role`` is
        # already ``select_related`` on ``_active_assignment`` so this stays a
        # zero-extra-query check, and matches the case-insensitive contract
        # documented in ``apps.common.role_names``.
        if rah is None or rah.role is None:
            return False
        return (rah.role.role_name or "").strip().lower() == expected_name

    def _student_profile(self, user):
        if user.id in self._cache_student:
            return self._cache_student[user.id]
        rah = self._active_assignment(user)
        profile = None
        if self._is_role(rah, ROLE_STUDENT):
            # Pull the linked supervisor + supervisor's user row in the same
            # query so the new supervisor_name / supervisor_email fields don't
            # add two extra round-trips per student.
            profile = (
                StudentProfile.objects
                .select_related("supervisor", "supervisor__user")
                .filter(user=user)
                .first()
            )
        self._cache_student[user.id] = profile
        return profile

    def _mentor_profile(self, user):
        if user.id in self._cache_mentor:
            return self._cache_mentor[user.id]
        rah = self._active_assignment(user)
        profile = None
        if self._is_role(rah, ROLE_MENTOR):
            profile = MentorProfile.objects.filter(user=user).first()
        self._cache_mentor[user.id] = profile
        return profile

    def _supervisor_profile(self, user):
        if user.id in self._cache_supervisor:
            return self._cache_supervisor[user.id]
        rah = self._active_assignment(user)
        profile = None
        if self._is_role(rah, ROLE_SUPERVISOR):
            profile = SupervisorProfile.objects.filter(user=user).first()
        self._cache_supervisor[user.id] = profile
        return profile

    def _interests(self, user):
        if user.id in self._cache_interests:
            return self._cache_interests[user.id]
        descs = list(
            UserInterest.objects
            .filter(user=user)
            .select_related("interest")
            .order_by("interest__interest_desc")
            .values_list("interest__interest_desc", flat=True)
        )
        self._cache_interests[user.id] = descs
        return descs

    # Annotation add to explicitly declare output type as drf-speculator cannot infer “unable to resolve type hint for..."
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_current_role_id(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None else rah.role_id

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_current_role_name(self, obj):
        rah = self._active_assignment(obj)
        return None if rah is None or rah.role is None else rah.role.role_name
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pg_firstname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_first_name
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pg_lastname(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_last_name

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_pg_email(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_email
    
    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_pg_email(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.pg_email

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_year_lvl(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.year_lvl
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_school_name(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.school_name
    
    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_join_perm(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.has_join_permission

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_joinperm_granted_at(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None else sp.joinperm_granted_at

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_join_perm_granted_at(self, obj):
        sp = self._student_profile(obj)
        return None if sp is None or sp.joinperm_granted_at is None else sp.joinperm_granted_at.isoformat()
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_pending_guardian(self, obj):
        sp = self._student_profile(obj)
        if sp is None or not sp.has_pending_guardian:
            return None
        return {
            "first_name": sp.pending_pg_first_name,
            "last_name": sp.pending_pg_last_name,
            "email": sp.pending_pg_email,
            "requested_at": sp.pending_pg_requested_at.isoformat(),
        }

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_ment_inst(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.institution
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_mentor_details(self, obj):
        """A mentor's details as their admin panel has them (their background,
        where they work or study, capacity, weekly times and groups), but not
        their application's answer; None for anyone else."""
        mp = self._mentor_profile(obj)
        if mp is None:
            return None
        from apps.admin.services.user import _mentor_dict, member_extras

        details = _mentor_dict(mp, member_extras([obj.pk])[obj.pk])
        details.pop("mentorReason", None)
        return details

    def get_ment_reason(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.mentor_reason
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ment_max_groups(self, obj):
        mp = self._mentor_profile(obj)
        return None if mp is None else mp.max_group_count

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_interests(self, obj):
        # Always a list (possibly empty); never null. Sorted alphabetically so
        # the FE can render a stable order without sorting client-side.
        return self._interests(obj)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_supervisor_name(self, obj):
        # Only meaningful for students; for everyone else (and for students
        # without a linked supervisor) we return null.
        sp = self._student_profile(obj)
        if sp is None or sp.supervisor_id is None or sp.supervisor.user is None:
            return None
        sup_user = sp.supervisor.user
        full_name = f"{sup_user.first_name} {sup_user.last_name}".strip()
        return full_name or None

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_supervisor_email(self, obj):
        sp = self._student_profile(obj)
        if sp is None or sp.supervisor_id is None or sp.supervisor.user is None:
            return None
        return sp.supervisor.user.email

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_supervisor_school_name(self, obj):
        # Only populated when the user themselves is currently in the
        # supervisor role. For students this stays null even though their
        # linked supervisor has a school name — that's exposed via the
        # student-side fields above.
        sp = self._supervisor_profile(obj)
        return None if sp is None else sp.school_name

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_supervised_students(self, obj):
        """Return the supervisor's active student registrations for their profile."""
        supervisor = self._supervisor_profile(obj)
        if supervisor is None:
            return []
        return [
            {
                "id": student.user_id,
                "first_name": student.user.first_name,
                "last_name": student.user.last_name,
                "email": student.user.email,
                "relationship_type": "student",
            }
            for student in (
                StudentProfile.objects
                .filter(supervisor=supervisor, user__account_status=User.AccountStatus.ACTIVE)
                .select_related("user")
                .order_by("user__last_name", "user__first_name", "user_id")
            )
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_profile_image_url(self, obj):
        from .profile_images import profile_image_url

        return profile_image_url(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_must_change_password(self, obj) -> bool:
        # Source of truth is Django's `has_usable_password()`. Users created via
        # the admin bulk-create / self-registration paths start with an unusable
        # password (they onboard via OTP / magic link), so this returns True
        # until they complete `AdminSetPasswordView`, `confirm_password_reset`,
        # or any other code path that calls `set_password(...)`. As soon as a
        # usable password exists this flips to False — exactly the contract the
        # FE asked for ("becomes false after they successfully update their
        # password"). This mirrors the signal already exposed to the admin
        # portal via `AdminPasswordStatusView.hasPassword` and so requires no
        # new schema / migration.
        return not obj.has_usable_password()


class SupervisedStudentEmailSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    kind = serializers.ChoiceField(choices=["guardian_details", "guardian_consent"])


class SupervisedStudentIdsSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class SupervisedStudentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    pronouns = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    country_id = serializers.IntegerField(allow_null=True)
    country_name = serializers.CharField(allow_blank=True)
    state_id = serializers.IntegerField(allow_null=True)
    state_name = serializers.CharField(allow_blank=True)
    account_status = serializers.CharField()
    media_consent = serializers.BooleanField(allow_null=True)
    media_consent_at = serializers.DateTimeField(allow_null=True)
    profile_image_url = serializers.CharField(allow_null=True, required=False)
    policies_agreed_at = serializers.DateTimeField(allow_null=True, required=False)
    school_name = serializers.CharField(allow_blank=True)
    year_lvl = serializers.CharField(allow_blank=True)
    interests = serializers.ListField(child=serializers.CharField())
    pg_first_name = serializers.CharField(allow_blank=True)
    pg_last_name = serializers.CharField(allow_blank=True)
    pg_email = serializers.EmailField(allow_blank=True, allow_null=True)
    parent_guardian_flag = serializers.BooleanField()
    has_join_permission = serializers.BooleanField()
    joinperm_response_id = serializers.CharField(allow_blank=True, allow_null=True)
    joinperm_granted_at = serializers.DateTimeField(allow_null=True)
    # No signature: fetched when a consent form is opened (SupervisedStudentSignaturesView).
    group_id = serializers.IntegerField(allow_null=True)
    group_name = serializers.CharField(allow_null=True)
    # Their group from registering, where My Groups' Waiting Area keeps them.
    registration_group_id = serializers.IntegerField(allow_null=True, required=False)


class SupervisedGroupMemberSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()


class SupervisedGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    group_name = serializers.CharField()
    members = SupervisedGroupMemberSerializer(many=True)
    interests = serializers.ListField(child=serializers.CharField())
    # "supervisor" or "members" for a group formed while registering, else "".
    registered_by = serializers.CharField(allow_blank=True)
    # Made a BIOTech group from My Groups' Waiting Area (Create all groups).
    placed = serializers.BooleanField(default=False)


class SupervisedGroupNameSerializer(serializers.Serializer):
    group_name = serializers.CharField(max_length=255)
    interests = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        required=False,
    )


class SupervisedGroupWriteSerializer(serializers.Serializer):
    group_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    interests = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        required=False,
    )


class SupervisedInterestCatalogSerializer(serializers.Serializer):
    interests = serializers.ListField(child=serializers.CharField())


class SupervisedGroupMemberChangeSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    role = serializers.ChoiceField(
        choices=["student", "mentor"],
        required=False,
        default="student",
    )


class SupervisedMentorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()


class StudentGuardianUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255, trim_whitespace=True)
    last_name = serializers.CharField(max_length=255, trim_whitespace=True)
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.strip().lower()
        user = self.context["request"].user
        if value == (user.email or "").strip().lower():
            raise serializers.ValidationError(
                "Enter your parent or guardian's email, not your own."
            )
        return value


class SupervisedStudentProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    # Blank leaves them unsaid, as registering allows.
    pronouns = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    # Where the student is, as their Personal information shows it.
    country_id = serializers.PrimaryKeyRelatedField(queryset=Countries.objects.all(), required=False, allow_null=True)
    state_id = serializers.PrimaryKeyRelatedField(queryset=CountryStates.objects.all(), required=False, allow_null=True)
    school_name = serializers.CharField(max_length=255)
    year_lvl = serializers.ChoiceField(choices=[(str(year), str(year)) for year in range(9, 13)])
    interests = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        required=False,
    )


class SupervisedStudentGuardianSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    pg_first_name = serializers.CharField(max_length=255)
    pg_last_name = serializers.CharField(max_length=255)
    pg_email = serializers.EmailField(required=False, allow_blank=True)
    # The supervisor confirmed the warning: a new guardian clears the
    # permission the old one gave.
    clear_permission = serializers.BooleanField(required=False, default=False)


class BulkUserStatusSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    account_status = serializers.ChoiceField(choices=User.AccountStatus.choices)


class AdminOperationsSummarySerializer(serializers.Serializer):
    active_users = serializers.IntegerField()
    invited_or_pending_users = serializers.IntegerField()
    suspended_or_deactivated_users = serializers.IntegerField()
    active_groups = serializers.IntegerField()
    groups_without_mentor = serializers.IntegerField()
    unassigned_match_recommendations = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
