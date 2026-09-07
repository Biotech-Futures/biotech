"""
TypeScript User Module Conversion to Python
Literal translation from admin/apps/server/src/module/user/
"""
import logging
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import Exists, OuterRef, Q, ProtectedError
from typing import List, Dict, Any, Optional

# Import models
from apps.users.models import (
    User, StudentProfile, SupervisorProfile, MentorProfile,
    AreasOfInterest, UserInterest, StudentSupervisor
)
from apps.tickets.models import SupportScope
from apps.users.models.admin_scope import AdminScope
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import (
    Countries, CountryStates, GroupAutoNameUnavailable, Groups, GroupMembership,
    group_name_sort_key,
)
from apps.groups.services import sync_supervisor_memberships_for_student
from apps.audit.services import log_audit_event

logger = logging.getLogger(__name__)

# What an admin is shown when something failed for a reason nobody wrote a
# sentence for.
#
# These paths used to interpolate str(exc) straight into `msg`, which is the
# field the admin app renders in a toast. On its own that looked harmless —
# nothing displayed it, because the frontend swallowed 4xx into a generic
# string. Then the frontend was fixed to show the server's own words (so that
# "Country cannot be cleared" and "Email already exists" would reach the
# person editing), and the two reasonable halves added up to Python exception
# text in a toast: table names, column names, whatever psycopg says.
#
# The deliberate refusals stay verbatim, because they are written for the
# reader. Only the "something blew up" cases are replaced, and the detail goes
# to the log where it is useful to us and invisible to them.
UNEXPECTED_FAILURE = (
    "Something went wrong saving that. Nothing was changed. "
    "If it keeps happening, tell the team what you were doing."
)


# ============================================================================
# CONSTANTS
# ============================================================================
# Every role the platform knows. "support" was missing from this list for two
# months after the role shipped: it was written in July, the client asked for a
# fifth role on 2026-09-04, and nothing brought the two together.
ROLES = ["student", "mentor", "supervisor", "admin", "support"]

# The subset a spreadsheet may create. Support and admin are left out on
# purpose: both hand out access to every ticket on a platform whose users are
# minors, and a bulk upload is the one path where nobody looks at the rows one
# at a time. Making an agent stays a deliberate act on the People page, which
# is also where the client asked for it ("similar to how they can currently
# create a new admin user").
BULK_IMPORTABLE_ROLES = ["student", "mentor", "supervisor"]


def role_rejection_message(role, allowed):
    """Why this role may not be used here, or None if it may.

    Two different refusals, because they need two different answers: a role
    that exists but is not allowed on this path tells the admin where to go
    instead, and a role that does not exist at all is a typo or a tampered
    payload.
    """
    if role in allowed:
        return None
    shown = role if isinstance(role, str) and role.strip() else "(blank)"
    if role in ROLES:
        return (f'"{shown}" accounts are created one at a time from the People '
                f'page, not by import.')
    return f'"{shown}" is not a role. Use one of: {", ".join(allowed)}.'

# The roles that carry no geography. One list, because the create path and the
# update path each had their own copy of this rule and they drifted the first
# time "support" was added: accounts could be created and then not saved.
#
# Nothing reads a support agent's or an admin's country. Ticket.region is a
# snapshot of the *requester's* country taken at submission
# (apps/tickets/services/lifecycle._region_snapshot), never the agent's.
# adminweb has its own copy of this list in src/type/user.ts, which is what
# decides whether the editor even shows the field.
ROLES_WITHOUT_GEOGRAPHY = ("admin", "support")

# Co-registration: friends who register together (same group number in the bulk
# upload) are placed in one group. Beyond this size we keep them together but warn.
CO_REGISTRATION_MAX_RECOMMENDED = 5
_CO_REGISTRATION_BLANK = {"", "none", "unassigned", "n/a", "na"}

_UNSET = object()  # sentinel: "not provided" vs explicit None/empty
STATUS_INVITED = User.AccountStatus.INVITED.value
STATUS_PENDING = User.AccountStatus.PENDING.value
STATUS_ACTIVE = User.AccountStatus.ACTIVE.value
STATUS_SUSPENDED = User.AccountStatus.SUSPENDED.value
STATUS_DEACTIVATED = User.AccountStatus.DEACTIVATED.value

DEFAULT_MENTOR_PROFILE = {
    "background": None,
    "institution": "",
    "mentor_reason": "",
    "max_group_count": 2,
}


# ============================================================================
# HELPER FUNCTIONS (shared.ts logic)
# ============================================================================

def normalize_interest_descriptions(interests: Optional[List[str]]) -> List[str]:
    """Normalize and deduplicate interest descriptions"""
    if not interests:
        return []
    trimmed = [item.strip() for item in interests if item.strip()]
    return list(dict.fromkeys(trimmed))  # Remove duplicates while preserving order


def resolve_role_id(role_name: str) -> int:
    """
    Get or create a role by name.
    Returns the role ID.
    """
    normalized_role = role_name.strip()
    role, created = Roles.objects.get_or_create(
        role_name__iexact=normalized_role,
        defaults={"role_name": normalized_role}
    )
    return role.id


def resolve_interest_ids(interests: Optional[List[str]]) -> List[int]:
    """
    Get or create interest IDs from descriptions.
    Returns list of interest IDs.
    """
    descriptions = normalize_interest_descriptions(interests)
    interest_ids = []
    
    for description in descriptions:
        interest, created = AreasOfInterest.objects.get_or_create(
            interest_desc__iexact=description,
            defaults={"interest_desc": description}
        )
        interest_ids.append(interest.id)
    
    return interest_ids


def sync_user_interests(user_id: int, interests: Optional[List[str]]) -> None:
    """
    Delete all existing user interests and create new ones from the list.
    """
    UserInterest.objects.filter(user_id=user_id).delete()
    
    interest_ids = resolve_interest_ids(interests)
    if not interest_ids:
        return
    
    bulk_interests = [
        UserInterest(user_id=user_id, interest_id=interest_id)
        for interest_id in interest_ids
    ]
    UserInterest.objects.bulk_create(bulk_interests)


def _resolve_supervisor_id(
    supervisor_email: Optional[str],
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    school_name: Optional[str] = None,
    state_id: Optional[int] = None,
    country_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve a student's supervisor to a SupervisorProfile id.

    Looks up an existing user by email; when a name is supplied (registration
    imports carry the supervisor's name) and no user exists, get_or_creates the
    supervisor User + supervisor role + SupervisorProfile. Returns None when
    there is nothing to link/create.

    A created supervisor inherits the student's country/state and lands active,
    matching how add_users_by_role creates every other user — imports carry no
    separate supervisor geography column, and the pair are always at the same school.
    """
    email = (supervisor_email or "").strip()
    if not email:
        return None

    sup_user = User.objects.filter(email__iexact=email).first()
    if sup_user is None:
        if not (first_name or last_name):
            return None  # lookup-only: no name to create a supervisor with
        now = timezone.now()
        sup_user = User.objects.create_user(
            email=email.lower(),
            first_name=(first_name or "").strip(),
            last_name=(last_name or "").strip(),
            password=None,
            country_id=country_id,
            state_id=state_id,
            is_active=True,
            account_status=STATUS_ACTIVE,
            invited_at=now,
            activated_at=now,
        )
        RoleAssignmentHistory.objects.create(
            user_id=sup_user.id,
            role_id=resolve_role_id("supervisor"),
            valid_from=now,
            valid_to=None,
        )
    else:
        # Backfill supervisors created before they inherited the student's geography.
        backfilled = []
        if country_id and sup_user.country_id is None:
            sup_user.country_id = country_id
            backfilled.append("country")
        if state_id and sup_user.state_id is None:
            sup_user.state_id = state_id
            backfilled.append("state")
        if backfilled:
            sup_user.save(update_fields=backfilled)

    sup_profile, _ = SupervisorProfile.objects.get_or_create(
        user_id=sup_user.id,
        defaults={"school_name": (school_name or "").strip() or None},
    )
    return sup_profile.user_id


def upsert_student_profile(
    user_id: int,
    first_name: str,
    last_name: str,
    school_name: Optional[str],
    year_level: Optional[int],
    supervisor_email: Any = _UNSET,
    supervisor_first_name: Optional[str] = None,
    supervisor_last_name: Optional[str] = None,
    guardian_first_name: Optional[str] = None,
    guardian_last_name: Optional[str] = None,
    guardian_email: Optional[str] = None,
    joinperm_response_id: Any = _UNSET,
    state_id: Optional[int] = None,
    country_id: Optional[int] = None,
) -> None:
    """
    Create or update student profile.

    Guardian names default to the student's own name when not supplied (keeps
    the single-create behaviour). supervisor_email=_UNSET leaves the link
    untouched; a value looks up — or, with a supervisor name, get_or_creates —
    the supervisor and also records the StudentSupervisor join. joinperm_response_id
    =_UNSET keeps the current consent state; a value (or blank) sets
    joinperm_responseID + has_join_permission.
    """
    profile_data = {
        "pg_first_name": (guardian_first_name or first_name),
        "pg_last_name": (guardian_last_name or last_name),
        "parent_guardian_flag": True,
        "school_name": (school_name or "").strip(),
        "year_lvl": str(year_level or ""),
    }
    if guardian_email is not None:
        profile_data["pg_email"] = (guardian_email or "").strip() or None

    if joinperm_response_id is not _UNSET:
        response_id = (joinperm_response_id or "").strip() or None
        profile_data["joinperm_responseID"] = response_id
        profile_data["has_join_permission"] = response_id is not None
    else:
        profile_data["has_join_permission"] = True
        profile_data["joinperm_responseID"] = None

    if supervisor_email is not _UNSET:
        profile_data["supervisor_id"] = _resolve_supervisor_id(
            supervisor_email,
            supervisor_first_name,
            supervisor_last_name,
            school_name,
            state_id,
            country_id,
        )

    student_profile, _ = StudentProfile.objects.update_or_create(
        user_id=user_id,
        defaults=profile_data,
    )

    supervisor_id = profile_data.get("supervisor_id")
    if supervisor_id:
        StudentSupervisor.objects.get_or_create(
            student_user_id=student_profile.user_id,
            supervisor_user_id=supervisor_id,
        )


def upsert_supervisor_profile(user_id: int, school_name: Optional[str] = None) -> None:
    """
    Create or update supervisor profile. School is optional.
    """
    SupervisorProfile.objects.update_or_create(
        user_id=user_id,
        defaults={"school_name": (school_name or "").strip() or None}
    )


def upsert_mentor_profile(
    user_id: int,
    background: Optional[str] = None,
    institution: Optional[str] = None,
    mentor_reason: Optional[str] = None,
    max_group_count: Optional[int] = None
) -> None:
    """
    Create or update mentor profile.
    """
    values = {**DEFAULT_MENTOR_PROFILE}
    
    if background is not None:
        values["background"] = background.strip() if background else None
    if institution is not None:
        values["institution"] = (institution or "").strip()
    if mentor_reason is not None:
        values["mentor_reason"] = (mentor_reason or "").strip()
    if max_group_count is not None:
        values["max_group_count"] = max_group_count
    
    MentorProfile.objects.update_or_create(
        user_id=user_id,
        defaults=values
    )


def ensure_admin_email_available(email: str) -> Optional[str]:
    """
    Check if email is already in use by any user.
    Returns error message if email exists, None otherwise.
    """
    if User.objects.filter(email=email).exists():
        return "Account email already exists"
    return None


def delete_student_details(user_id: int) -> None:
    """Delete student profile for a user"""
    StudentProfile.objects.filter(user_id=user_id).delete()


def delete_user_interests(user_id: int) -> None:
    """Delete all interests for a user"""
    UserInterest.objects.filter(user_id=user_id).delete()


def rollback_created_user(user_id: int) -> None:
    """
    Rollback user creation (delete user and related records).
    """
    with transaction.atomic():
        RoleAssignmentHistory.objects.filter(user_id=user_id).delete()
        User.objects.filter(id=user_id).delete()


def _user_country_dict(user: User) -> Optional[Dict[str, Any]]:
    """Serialize the user's country for the admin API, or None."""
    if not user.country_id:
        return None
    return {"id": user.country.id, "countryName": user.country.country_name}


def _user_state_dict(user: User) -> Optional[Dict[str, Any]]:
    """Serialize the user's sub-national state for the admin API, or None.

    Blank for most non-Australian users — country is on its own field. The state's
    own country is deliberately not echoed here: `country` is the single source of
    truth, and a second copy could only ever disagree with it.
    """
    if not user.state_id:
        return None
    state = user.state
    return {
        "id": state.id,
        "stateName": state.state_name,
    }


def build_user_dict(user: User, role_str: Optional[str] = None,
                   state: Optional[Dict[str, Any]] = None,
                   group_name: Optional[str] = None,
                   student_profile: Optional[StudentProfile] = None,
                   supervisor_profile: Optional[SupervisorProfile] = None,
                   mentor_profile: Optional[MentorProfile] = None,
                   is_admin: bool = False,
                   supervisor_name: Optional[str] = None,
                   supervisor_email_val: Optional[str] = None,
                   supervisees: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Build a user dictionary with all related data.
    """
    # Get current role if not provided
    if role_str is None:
        now = timezone.now()
        current_role = RoleAssignmentHistory.objects.filter(
            user_id=user.id
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).select_related('role').first()
        role_str = current_role.role.role_name if current_role else None
    
    # Get current group if not provided
    if group_name is None:
        group_membership = GroupMembership.objects.filter(
            user_id=user.id,
            left_at__isnull=True
        ).select_related('group').first()
        if group_membership and not group_membership.group.deleted_at:
            group_name = group_membership.group.group_name
    
    # Get interests
    interests = list(
        UserInterest.objects.filter(user_id=user.id)
        .values_list('interest__interest_desc', flat=True)
    )
    
    # Get school name from either student or supervisor profile
    school_name = None
    if student_profile and student_profile.school_name:
        school_name = student_profile.school_name
    elif supervisor_profile and supervisor_profile.school_name:
        school_name = supervisor_profile.school_name
    
    return {
        "id": user.id,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email,
        "role": role_str,
        "country": _user_country_dict(user),
        "state": state,
        "groupName": group_name,
        "schoolName": school_name,
        "mentorBackground": mentor_profile.background if mentor_profile else None,
        "mentorInstitution": mentor_profile.institution if mentor_profile else None,
        "mentorReason": mentor_profile.mentor_reason if mentor_profile else None,
        "mentorMaxGroupCount": mentor_profile.max_group_count if mentor_profile else None,
        "yearLevel": int(student_profile.year_lvl) if student_profile and student_profile.year_lvl else None,
        "joinPermissionReceived": student_profile.has_join_permission if student_profile else False,
        "interests": interests,
        "isAdmin": is_admin,
        "isActive": user.is_active,
        "hasLoggedIn": user.last_login is not None,
        "lastLogin": user.last_login.isoformat() if user.last_login else None,
        "accountStatus": "active" if user.is_active else "deactivated",
        "invitedAt": user.invited_at.isoformat() if user.invited_at else None,
        "activatedAt": user.activated_at.isoformat() if user.activated_at else None,
        "supervisorName": supervisor_name,
        "supervisorEmail": supervisor_email_val,
        "supervisees": supervisees or [],
    }


def fetch_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch complete user data by ID with all related profiles.
    """
    try:
        user = User.objects.select_related('country', 'state').get(id=user_id)
    except User.DoesNotExist:
        return None

    student_profile = StudentProfile.objects.filter(user_id=user_id).first()
    supervisor_profile = SupervisorProfile.objects.filter(user_id=user_id).first()
    mentor_profile = MentorProfile.objects.filter(user_id=user_id).first()
    user_is_admin = is_admin_user(user_id)

    state = _user_state_dict(user)

    # Resolve current role so we can fetch the right extra data
    now = timezone.now()
    current_role_obj = RoleAssignmentHistory.objects.filter(
        user_id=user_id
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related('role').first()
    role_str = current_role_obj.role.role_name if current_role_obj else None

    # Supervisor info for students
    supervisor_name = None
    supervisor_email_val = None
    if role_str == "student" and student_profile and student_profile.supervisor_id:
        try:
            sup_profile = SupervisorProfile.objects.select_related('user').get(
                user_id=student_profile.supervisor_id
            )
            supervisor_name = f"{sup_profile.user.first_name} {sup_profile.user.last_name}".strip()
            supervisor_email_val = sup_profile.user.email
        except SupervisorProfile.DoesNotExist:
            pass

    # Supervisee info for supervisors
    supervisees: List[Dict[str, Any]] = []
    if role_str == "supervisor" and supervisor_profile:
        for sp in StudentProfile.objects.filter(
            supervisor_id=supervisor_profile.user_id
        ).select_related('user'):
            supervisees.append({
                "name": f"{sp.user.first_name} {sp.user.last_name}".strip(),
                "email": sp.user.email,
            })

    return build_user_dict(
        user,
        role_str=role_str,
        state=state,
        student_profile=student_profile,
        supervisor_profile=supervisor_profile,
        mentor_profile=mentor_profile,
        is_admin=user_is_admin,
        supervisor_name=supervisor_name,
        supervisor_email_val=supervisor_email_val,
        supervisees=supervisees,
    )


def is_admin_user(user_id: int) -> bool:
    return AdminScope.objects.filter(user_id=user_id).exists()


def get_admin_user_ids(user_ids: List[int]) -> set:
    if not user_ids:
        return set()
    return set(
        AdminScope.objects.filter(user_id__in=user_ids).values_list("user_id", flat=True)
    )


# ============================================================================
# QUERY FUNCTIONS (query.ts logic)
# ============================================================================

def _build_user_filter_queryset(search: Optional[str] = None, role: Optional[str] = None,
                                state: Optional[str] = None, active: Optional[bool] = None,
                                in_group: Optional[str] = None, country: Optional[str] = None):
    """Filtered (unpaginated) user queryset shared by the list view and
    filter-based bulk actions, so 'select all matching' hits exactly the rows
    the list would show for the same filters."""
    now = timezone.now()
    filters = Q()

    if search:
        normalized_search = search.strip()
        filters &= (
            Q(first_name__icontains=normalized_search) |
            Q(last_name__icontains=normalized_search) |
            Q(email__icontains=normalized_search) |
            Q(groupmembership__group__group_name__icontains=normalized_search)
        )

    if role:
        filters &= Q(roleassignmenthistory__role__role_name=role) & (
            Q(roleassignmenthistory__valid_to__isnull=True) |
            Q(roleassignmenthistory__valid_to__gte=now)
        )

    if country:
        filters &= Q(country__country_name=country)

    # State names are unique only per country, so pair with country when both are set.
    if state:
        filters &= Q(state__state_name=state)

    if active is not None:
        filters &= Q(is_active=active)

    return _filter_by_active_group_membership(
        User.objects.filter(filters),
        in_group,
    )


def query_users(page: int = 1, limit: int = 10, search: Optional[str] = None,
               role: Optional[str] = None, state: Optional[str] = None,
               active: Optional[bool] = None, in_group: Optional[str] = None,
               sort_by: str = "createdAt", sort_order: str = "desc",
               requesting_user=None, country: Optional[str] = None) -> Dict[str, Any]:
    """
    Query users with pagination and filters.
    """
    offset = (page - 1) * limit

    queryset = _build_user_filter_queryset(
        search=search, role=role, state=state, active=active, in_group=in_group,
        country=country,
    )

    # Get total count
    total = queryset.values('id').distinct().count()

    # Determine sort order. Keep the public API keys aligned with adminweb.
    sort_map = {
        "name": ["first_name", "last_name", "id"],
        "email": ["email", "id"],
        "role": ["roleassignmenthistory__role__role_name", "first_name", "last_name", "id"],
        "country": ["country__country_name", "first_name", "last_name", "id"],
        "state": ["state__state_name", "first_name", "last_name", "id"],
        "status": ["is_active", "first_name", "last_name", "id"],
        "school": ["studentprofile__school_name", "first_name", "last_name", "id"],
        "yearLevel": ["studentprofile__year_lvl", "first_name", "last_name", "id"],
        # Padded key, not the raw column: unpadded auto-names sort "BTF10" before "BTF9".
        "group": ["group_name_key", "first_name", "last_name", "id"],
        "createdAt": ["date_joined", "id"],
        "lastLogin": ["last_login", "first_name", "last_name", "id"],
        "hasLoggedIn": ["last_login", "first_name", "last_name", "id"],
    }
    order_by = sort_map.get(sort_by, sort_map["createdAt"])

    if sort_order == "desc":
        order_by = [f"-{field}" if field != "id" else field for field in order_by]

    if sort_by == "group":
        queryset = queryset.annotate(
            group_name_key=group_name_sort_key("groupmembership__group__group_name")
        )

    # Get paginated user IDs
    user_ids = list(
        queryset
        .values_list('id', flat=True)
        .distinct()
        .order_by(*order_by)[offset:offset + limit]
    )

    if not user_ids:
        return {
            "msg": "Users retrieved successfully",
            "data": {
                "items": [],
                "total": total,
                "page": page,
                "limit": limit,
                "hasMore": False,
            }
        }

    # Bulk fetch all related data (6 queries instead of ~8 per user)
    users_by_id = {
        u.id: u for u in User.objects.filter(id__in=user_ids).select_related('country', 'state')
    }

    student_profiles = {
        sp.user_id: sp for sp in StudentProfile.objects.filter(user_id__in=user_ids)
    }
    supervisor_profiles = {
        sp.user_id: sp for sp in SupervisorProfile.objects.filter(user_id__in=user_ids)
    }
    mentor_profiles = {
        mp.user_id: mp for mp in MentorProfile.objects.filter(user_id__in=user_ids)
    }
    admin_user_ids = get_admin_user_ids(user_ids)

    # Active role assignments
    now = timezone.now()
    role_map = {}
    for rah in RoleAssignmentHistory.objects.filter(
        user_id__in=user_ids
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related('role'):
        role_map[rah.user_id] = rah.role.role_name

    # Active group memberships
    group_map = {}
    for gm in GroupMembership.objects.filter(
        user_id__in=user_ids, left_at__isnull=True
    ).select_related('group'):
        if not gm.group.deleted_at:
            group_map[gm.user_id] = {
                "id": gm.group.id,
                "name": gm.group.group_name,
            }

    # User interests — plain strings to match build_user_dict
    interests_map: Dict[int, List[str]] = {}
    for ui in UserInterest.objects.filter(user_id__in=user_ids).select_related('interest'):
        interests_map.setdefault(ui.user_id, []).append(ui.interest.interest_desc)

    # Supervisor info for students: collect all supervisor_profile_ids referenced by students
    # Note: SupervisorProfile pk is user_id, so supervisor_id on StudentProfile holds user_id
    student_supervisor_profile_ids = [
        sp.supervisor_id for sp in student_profiles.values() if sp.supervisor_id
    ]
    supervisor_profile_by_id: Dict[int, Any] = {}
    if student_supervisor_profile_ids:
        for sup_prof in SupervisorProfile.objects.filter(
            user_id__in=student_supervisor_profile_ids
        ).select_related('user'):
            supervisor_profile_by_id[sup_prof.user_id] = sup_prof

    # Supervisee info for supervisors: one query for all supervisors on this page
    sup_profile_ids_on_page = [
        supervisor_profiles[uid].user_id for uid in user_ids if uid in supervisor_profiles
    ]
    supervisee_map: Dict[int, List[Dict[str, Any]]] = {}  # supervisor user_id -> list
    if sup_profile_ids_on_page:
        for student_sp in StudentProfile.objects.filter(
            supervisor_id__in=sup_profile_ids_on_page
        ).select_related('user'):
            supervisee_map.setdefault(student_sp.supervisor_id, []).append({
                "name": f"{student_sp.user.first_name} {student_sp.user.last_name}".strip(),
                "email": student_sp.user.email,
            })

    # Build response in original user_ids order
    users_list = []
    for uid in user_ids:
        user = users_by_id.get(uid)
        if not user:
            continue

        sp = student_profiles.get(uid)
        supervisor = supervisor_profiles.get(uid)
        mp = mentor_profiles.get(uid)
        school_name = None
        if sp and sp.school_name:
            school_name = sp.school_name
        elif supervisor and supervisor.school_name:
            school_name = supervisor.school_name

        # Resolve supervisor name/email for students
        supervisor_name = None
        supervisor_email_val = None
        if sp and sp.supervisor_id and sp.supervisor_id in supervisor_profile_by_id:
            sup_prof = supervisor_profile_by_id[sp.supervisor_id]
            supervisor_name = f"{sup_prof.user.first_name} {sup_prof.user.last_name}".strip()
            supervisor_email_val = sup_prof.user.email

        # Resolve supervisees for supervisors
        supervisees_for_user = supervisee_map.get(supervisor.user_id, []) if supervisor else []

        group_info = group_map.get(uid)
        users_list.append({
            "id": user.id,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "email": user.email,
            "role": role_map.get(uid),
            "country": _user_country_dict(user),
            "state": _user_state_dict(user),
            "groupId": group_info["id"] if group_info else None,
            "groupName": group_info["name"] if group_info else None,
            "schoolName": school_name,
            "mentorBackground": mp.background if mp else None,
            "mentorInstitution": mp.institution if mp else None,
            "mentorReason": mp.mentor_reason if mp else None,
            "mentorMaxGroupCount": mp.max_group_count if mp else None,
            "yearLevel": int(sp.year_lvl) if sp and sp.year_lvl else None,
            "joinPermissionReceived": sp.has_join_permission if sp else False,
            "interests": interests_map.get(uid, []),
            "isAdmin": uid in admin_user_ids,
            "isActive": user.is_active,
            "hasLoggedIn": user.last_login is not None,
            "lastLogin": user.last_login.isoformat() if user.last_login else None,
            "accountStatus": "active" if user.is_active else "deactivated",
            "invitedAt": user.invited_at.isoformat() if user.invited_at else None,
            "activatedAt": user.activated_at.isoformat() if user.activated_at else None,
            "supervisorName": supervisor_name,
            "supervisorEmail": supervisor_email_val,
            "supervisees": supervisees_for_user,
        })

    return {
        "msg": "Users retrieved successfully",
        "data": {
            "items": users_list,
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": offset + len(users_list) < total,
        }
    }


def query_user_by_id(user_id: int) -> Dict[str, Any]:
    """
    Query a single user by ID.
    """
    user = fetch_user_by_id(user_id)
    if not user:
        return {"msg": "User not found", "data": None}
    return {"msg": "User retrieved successfully", "data": user}


def query_countries(requesting_user=None, in_use: bool = False) -> Dict[str, Any]:
    """Get countries for assignment, or with in_use=True only those that have users.

    Reads the Countries lookup directly — deriving this from the states list would
    drop every country whose users have no sub-national region (i.e. most of them).
    in_use keeps the filter dropdowns to countries that can actually return rows;
    assignment still needs the full list.
    """
    queryset = Countries.objects.order_by("country_name")
    if in_use:
        queryset = queryset.filter(users__isnull=False).distinct()
    items = [
        {"id": c["id"], "countryName": c["country_name"]}
        for c in queryset.values("id", "country_name")
    ]
    return {"msg": "Countries retrieved successfully", "data": items}


def query_states(requesting_user=None) -> Dict[str, Any]:
    """Get all states/regions for filtering and assignment."""
    states_list = (
        CountryStates.objects.select_related("country")
        .order_by("country__country_name", "state_name")
        .values("id", "state_name", "country__country_name")
    )
    items = [
        {
            "id": s["id"],
            "stateName": s["state_name"],
            "countryName": s["country__country_name"],
        }
        for s in states_list
    ]
    return {"msg": "States retrieved successfully", "data": items}


def _filter_by_active_group_membership(queryset, in_group: Optional[str]):
    active_membership = GroupMembership.objects.filter(
        user_id=OuterRef("pk"),
        left_at__isnull=True,
        group__deleted_at__isnull=True,
    )

    if in_group == "yes":
        return queryset.annotate(has_active_group=Exists(active_membership)).filter(
            has_active_group=True
        )
    if in_group == "no":
        return queryset.annotate(has_active_group=Exists(active_membership)).filter(
            has_active_group=False
        )
    return queryset


# ============================================================================
# MUTATION FUNCTIONS (mutation.ts logic)
# ============================================================================

def add_users_by_role(
    inputs: List[Dict[str, Any]], initiated_by=None, allowed_roles=None
) -> List[Dict[str, Any]]:
    """Bulk create users with validation and role-specific setup.

    ``allowed_roles`` is the set of roles this caller may create, and it is
    checked here rather than at each view because here is where every path
    meets. The role was previously only ever checked by BulkUserRowSerializer,
    which one of the two bulk endpoints uses: the JSON one refused
    ``role: support`` and the CSV one beside it created the account, granted
    queue access and left the audit row with no actor. ``resolve_role_id`` is a
    get_or_create, so an unknown role did not fail either — it added a row to
    the roles table and carried on.
    """
    allowed = list(ROLES if allowed_roles is None else allowed_roles)
    results = []
    now = timezone.now()
    
    for input_data in inputs:
        email = input_data.get("email", "").lower().strip()
        first_name = input_data.get("firstName", "")
        last_name = input_data.get("lastName", "")
        role = input_data.get("role", "student")
        country_name = (input_data.get("country") or "").strip()
        state_name = (input_data.get("state") or "").strip()

        refusal = role_rejection_message(role, allowed)
        if refusal is not None:
            results.append({"input": input_data, "msg": refusal, "data": None})
            continue

        # Check if user exists
        if User.objects.filter(email=email).exists():
            results.append({
                "input": input_data,
                "msg": "Email already exists",
                "data": None
            })
            continue
        
        # Validate geography for non-admin users. Country is the required field;
        # state is optional. A bare state still resolves a country (see below), so
        # accept either.
        #
        # "support" is exempt for the same reason "admin" is: the client asked
        # for support agents to be created "similar to how they can currently
        # create a new admin user", and that form asks for a name, an email and
        # a role. Nothing reads an agent's country either — Ticket.region is a
        # snapshot of the *requester's* country, taken at submission
        # (apps/tickets/services/lifecycle._region_snapshot), so asking for one
        # here would be asking for a fact no code ever looks at.
        if role not in ROLES_WITHOUT_GEOGRAPHY and not country_name and not state_name:
            results.append({
                "input": input_data,
                "msg": "Country is required",
                "data": None
            })
            continue
        
        # Validate student-specific fields
        if role == "student":
            school_name = (input_data.get("schoolName") or "").strip()
            year_level = input_data.get("yearLevel")
            
            if not school_name:
                results.append({
                    "input": input_data,
                    "msg": "School is required for student users",
                    "data": None
                })
                continue
            
            if not year_level:
                results.append({
                    "input": input_data,
                    "msg": "Year level is required for student users",
                    "data": None
                })
                continue
        
        # Validate mentor-specific fields
        if role == "mentor":
            institution = (input_data.get("mentorInstitution") or "").strip()
            reason = (input_data.get("mentorReason") or "").strip()
            max_count = input_data.get("mentorMaxGroupCount")
            interests = input_data.get("interests") or []
            
            if not institution:
                results.append({
                    "input": input_data,
                    "msg": "Institution is required for mentor users",
                    "data": None
                })
                continue
            
            if not reason:
                results.append({
                    "input": input_data,
                    "msg": "Mentor reason is required for mentor users",
                    "data": None
                })
                continue
            
            if max_count is None:
                results.append({
                    "input": input_data,
                    "msg": "Max group count is required for mentor users",
                    "data": None
                })
                continue
            
            if not interests:
                results.append({
                    "input": input_data,
                    "msg": "At least one interest is required for mentor users",
                    "data": None
                })
                continue
        
        # Validate interests for student/mentor
        if role in ["student", "mentor"]:
            interests = input_data.get("interests") or []
            if not interests:
                results.append({
                    "input": input_data,
                    "msg": f"At least one interest is required for {role} users",
                    "data": None
                })
                continue
        
        # Resolve country + state. Country is what matching needs and is
        # get_or_create'd so international registrants import cleanly. State is the
        # sub-national region — blank unless the export carries one, and never the
        # country name wearing a state's hat.
        country_obj = None
        state_obj = None
        if country_name:
            # iexact so a casing variant in one export ("australia") can't fork a
            # second country off the real one.
            country_obj, _ = Countries.objects.get_or_create(
                country_name__iexact=country_name,
                defaults={"country_name": country_name},
            )
            if state_name and state_name.casefold() != country_name.casefold():
                state_obj, _ = CountryStates.objects.get_or_create(
                    country=country_obj, state_name=state_name
                )
        elif state_name:
            # Callers that send a state name only (the single-create form): derive
            # the country from the state row.
            state_obj = CountryStates.objects.filter(
                state_name=state_name
            ).select_related("country").first()
            if state_obj is None:
                results.append({
                    "input": input_data,
                    "msg": f'State "{state_name}" not found',
                    "data": None
                })
                continue
            country_obj = state_obj.country
        country_id = country_obj.id if country_obj else None
        state_id = state_obj.id if state_obj else None
        
        # Resolve role ID
        try:
            role_id = resolve_role_id(role)
        except Exception as e:
            logger.exception("admin.user.resolve_role_failed role=%s", role)
            results.append({
                "input": input_data,
                "msg": UNEXPECTED_FAILURE,
                "data": None
            })
            continue
        
        # Check admin email
        if role == "admin":
            admin_email_error = ensure_admin_email_available(email)
            if admin_email_error:
                results.append({
                    "input": input_data,
                    "msg": admin_email_error,
                    "data": None
                })
                continue
        
        # Create user in transaction
        try:
            with transaction.atomic():
                # Determine account status
                is_active = input_data.get("active", True)
                account_status = STATUS_ACTIVE if is_active else STATUS_INVITED
                
                # Create user
                user = User.objects.create_user(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=None,  # No password set
                    country_id=country_id,
                    state_id=state_id,
                    is_active=is_active,
                    account_status=account_status,
                    is_staff=role == "admin",
                    is_superuser=role == "admin",
                    invited_at=now,
                    activated_at=now if is_active else None,
                )
                
                new_user_id = user.id
                
                # Create role assignment
                RoleAssignmentHistory.objects.create(
                    user_id=new_user_id,
                    role_id=role_id,
                    valid_from=now,
                    valid_to=None
                )
                
                # Create role-specific profiles
                if role == "student":
                    upsert_student_profile(
                        new_user_id,
                        first_name,
                        last_name,
                        input_data.get("schoolName"),
                        input_data.get("yearLevel"),
                        supervisor_email=input_data.get("supervisorEmail") or _UNSET,
                        supervisor_first_name=input_data.get("supervisorFirstName"),
                        supervisor_last_name=input_data.get("supervisorLastName"),
                        guardian_first_name=input_data.get("guardianFirstName"),
                        guardian_last_name=input_data.get("guardianLastName"),
                        guardian_email=input_data.get("guardianEmail"),
                        joinperm_response_id=input_data.get(
                            "joinpermResponseId", _UNSET
                        ),
                        state_id=state_id,
                        country_id=country_id,
                    )
                
                if role == "supervisor":
                    upsert_supervisor_profile(
                        new_user_id,
                        (input_data.get("supervisorSchoolName") or "").strip()
                    )
                
                if role == "mentor":
                    upsert_mentor_profile(
                        new_user_id,
                        background=input_data.get("mentorBackground"),
                        institution=input_data.get("mentorInstitution"),
                        mentor_reason=input_data.get("mentorReason"),
                        max_group_count=input_data.get("mentorMaxGroupCount")
                    )
                
                # Sync interests
                if role in ["student", "mentor"]:
                    sync_user_interests(new_user_id, input_data.get("interests"))
        
        except Exception as e:
            logger.exception("admin.user.create_failed role=%s", role)
            results.append({
                "input": input_data,
                "msg": UNEXPECTED_FAILURE,
                "data": None
            })
            continue
        
        # Mark admin users
        if role == "admin":
            try:
                AdminScope.objects.get_or_create(user_id=new_user_id)
            except Exception as e:
                logger.exception("admin.user.admin_scope_failed user=%s", new_user_id)
                rollback_created_user(new_user_id)
                results.append({
                    "input": input_data,
                    "msg": UNEXPECTED_FAILURE,
                    "data": None
                })
                continue

        # Mark support agents.
        #
        # Asked on 2026-09-04 where support agents come from, the client
        # answered: "The admin would create a new account for the support
        # agent, similar to how they can currently create a new admin user, but
        # rather assign the support role to them." So this mirrors the block
        # above, one table across.
        #
        # A SupportScope row and NOT an AdminScope row, and the user is not
        # is_staff either. That is the whole point of the role: the client's
        # own note on p47 is "all admins have support access, but not all
        # support are admins", and an agent created here can work the ticket
        # queue and nothing else in the admin app.
        #
        # Placed outside the transaction that created the user, matching the
        # admin block rather than the tidier alternative, so that a failure
        # here rolls the account back the same way and leaves the same kind of
        # message behind.
        if role == "support":
            try:
                # The grant and the row that says who made it go in together.
                # The roster grant at apps/tickets/views_admin.SupportScopeView
                # writes both of these in one transaction for the same reason:
                # half the ways of giving somebody queue access recorded and
                # half not would leave "who let this person into the queue"
                # with no answer, on a platform whose users are minors. Split
                # in two, a failure on the audit write left the account made,
                # the access live, nothing in the log, a 500 on the admin's
                # screen, and no way to finish the job from the interface,
                # because the retry met "Email already exists".
                with transaction.atomic():
                    SupportScope.objects.get_or_create(user_id=new_user_id)
                    log_audit_event(
                        actor=initiated_by,
                        entity_type="support_scope",
                        entity_id=new_user_id,
                        action="create",
                        before_state=None,
                        after_state={"user_id": new_user_id, "via": "user_creation"},
                    )
            except Exception as e:
                logger.exception("admin.user.support_scope_failed user=%s", new_user_id)
                rollback_created_user(new_user_id)
                results.append({
                    "input": input_data,
                    "msg": UNEXPECTED_FAILURE,
                    "data": None
                })
                continue
        
        # Fetch created user
        created_user = fetch_user_by_id(new_user_id)
        results.append({
            "input": input_data,
            "msg": "User created successfully",
            "data": created_user
        })
    
    return results


def create_user(input_data: Dict[str, Any], initiated_by=None) -> Dict[str, Any]:
    """
    Create a single user.

    ``initiated_by`` is only used to attribute the support-access audit row —
    creating a user is not itself audited today, for any role, and this change
    does not start doing that. It records the *privilege grant*, which the
    roster page already records when it hands out the same access.
    """
    results = add_users_by_role([input_data], initiated_by=initiated_by)
    result = results[0]
    return {"msg": result["msg"], "data": result["data"]}


def _apply_co_registration(
    users_input: List[Dict[str, Any]], created_student_emails: set
) -> Dict[str, Any]:
    """Place students that share a group number (co-registered friends) into one group.

    Only students created in this batch are grouped; a group number used by a single
    student falls back to normal matching. Groups larger than the recommended size are
    kept together with a warning. Creating the membership here also exempts these
    students from auto-matching, whose pool excludes anyone with an active membership.
    """
    buckets: Dict[str, List[int]] = {}
    for input_data in users_input:
        if (input_data.get("role") or "student") != "student":
            continue
        # A "group number" is naturally numeric, so coerce rather than assume str.
        raw_group_number = input_data.get("groupNumber")
        group_number = ("" if raw_group_number is None else str(raw_group_number)).strip()
        if not group_number or group_number.lower() in _CO_REGISTRATION_BLANK:
            continue
        email = (input_data.get("email") or "").lower().strip()
        if email not in created_student_emails:
            continue
        user = User.objects.filter(email=email).first()
        if user:
            buckets.setdefault(group_number, []).append(user.id)

    groups_created: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for group_number, user_ids in buckets.items():
        # de-dupe while preserving order
        member_ids = list(dict.fromkeys(user_ids))
        if len(member_ids) < 2:
            continue

        try:
            with transaction.atomic():
                # Co-registered groups draw from the same BTF<n> series as every other auto-name.
                group = Groups.create_auto_named()
                GroupMembership.objects.bulk_create([
                    GroupMembership(
                        group=group,
                        user_id=uid,
                        membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                    )
                    for uid in member_ids
                ])
        except GroupAutoNameUnavailable as exc:
            # One unusable auto-name must not abort the whole import.
            warnings.append(
                f'Group number "{group_number}" ({len(member_ids)} students) could not '
                f"be created: {exc} Those students were left ungrouped."
            )
            continue

        # Attach supervisors to the new group, mirroring the matching-confirm flow.
        for uid in member_ids:
            sync_supervisor_memberships_for_student(uid)

        groups_created.append({"name": group.group_name, "memberCount": len(member_ids)})
        if len(member_ids) > CO_REGISTRATION_MAX_RECOMMENDED:
            warnings.append(
                f'"{group.group_name}" has {len(member_ids)} members '
                f'(over the recommended {CO_REGISTRATION_MAX_RECOMMENDED}).'
            )

    return {"groupsCreated": groups_created, "warnings": warnings}


def bulk_create_users(
    users_input: List[Dict[str, Any]], admin_user_id: str, initiated_by=None
) -> Dict[str, Any]:
    """Bulk create users from list.

    Restricted to BULK_IMPORTABLE_ROLES: an import is the one path where no
    one reads the rows individually. ``initiated_by`` is passed on so that a
    privilege granted through here has a name against it — without it the
    audit row said only that access had been given, not by whom.
    """
    created = []
    skipped = []
    created_student_emails = set()

    results = add_users_by_role(
        users_input,
        initiated_by=initiated_by,
        allowed_roles=BULK_IMPORTABLE_ROLES,
    )

    for result in results:
        if result["data"]:
            created.append(result["data"])
            if (result["input"].get("role") or "student") == "student":
                email = (result["input"].get("email") or "").lower().strip()
                if email:
                    created_student_emails.add(email)
        else:
            skipped.append({
                "email": result["input"].get("email", "unknown"),
                "reason": result.get("msg", "Skipped"),
            })

    # Second pass: fix supervisor links for students where the supervisor was also
    # created in this same batch and may not have existed when the student was processed.
    for input_data in users_input:
        if input_data.get("role") == "student" and input_data.get("supervisorEmail"):
            email = (input_data.get("email") or "").lower().strip()
            student_user = User.objects.filter(email=email).first()
            if not student_user:
                continue
            sup_email = input_data["supervisorEmail"].strip()
            sup_user = User.objects.filter(email__iexact=sup_email).first()
            if not sup_user:
                continue
            sup_profile = SupervisorProfile.objects.filter(user_id=sup_user.id).first()
            if sup_profile:
                StudentProfile.objects.filter(user_id=student_user.id).update(
                    supervisor_id=sup_profile.user_id
                )

    # Third pass: group co-registered students (shared group number) into one group.
    # Runs after the supervisor pass so supervisor links are set before syncing them.
    co_registration = _apply_co_registration(users_input, created_student_emails)

    msg = f"Bulk import complete: {len(created)} created, {len(skipped)} skipped"
    data = {"created": created, "skipped": skipped}
    if co_registration["groupsCreated"]:
        count = len(co_registration["groupsCreated"])
        msg += f", {count} co-registration group{'s' if count != 1 else ''} created"
    # Warnings must survive even when no group was created, or a run that failed
    # every group would report a clean import.
    if co_registration["groupsCreated"] or co_registration["warnings"]:
        data["coRegistration"] = co_registration

    return {"msg": msg, "data": data}


def update_user(user_id: int, input_data: Dict[str, Any], initiated_by=None) -> Dict[str, Any]:
    """
    Update user information and role.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"msg": "User not found", "data": None}
    
    now = timezone.now()
    current_role_assignment = (
        RoleAssignmentHistory.objects.filter(
            user_id=user_id
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        )
        .select_related('role')
        .first()
    )
    current_role = (
        current_role_assignment.role.role_name
        if current_role_assignment and current_role_assignment.role
        else None
    )
    next_role = input_data.get("role") or current_role or "student"
    
    # Check email change
    if "email" in input_data:
        new_email = input_data["email"].strip().lower()
        if new_email != user.email.lower():
            return {"msg": "Email cannot be changed", "data": None}
    
    # Validate role-specific requirements
    next_interests = input_data.get("interests") or (
        list(UserInterest.objects.filter(user_id=user_id)
            .values_list('interest__interest_desc', flat=True))
    )
    
    if next_role == "student":
        next_school = input_data.get("schoolName") or (
            StudentProfile.objects.filter(user_id=user_id).values_list(
                'school_name', flat=True
            ).first()
        )
        next_year = input_data.get("yearLevel") or (
            StudentProfile.objects.filter(user_id=user_id).values_list(
                'year_lvl', flat=True
            ).first()
        )
        
        if not (next_school or "").strip():
            return {"msg": "School is required for student users", "data": None}
        if not next_year:
            return {"msg": "Year level is required for student users", "data": None}
    
    if next_role in ["student", "mentor"] and not next_interests:
        return {
            "msg": f"At least one interest is required for {next_role} users",
            "data": None
        }
    
    if next_role == "mentor":
        next_institution = input_data.get("mentorInstitution") or (
            MentorProfile.objects.filter(user_id=user_id).values_list(
                'institution', flat=True
            ).first()
        )
        next_reason = input_data.get("mentorReason") or (
            MentorProfile.objects.filter(user_id=user_id).values_list(
                'mentor_reason', flat=True
            ).first()
        )
        next_max_count = input_data.get("mentorMaxGroupCount") or (
            MentorProfile.objects.filter(user_id=user_id).values_list(
                'max_group_count', flat=True
            ).first()
        )
        
        if not (next_institution or "").strip():
            return {"msg": "Institution is required for mentor users", "data": None}
        if not (next_reason or "").strip():
            return {"msg": "Mentor reason is required for mentor users", "data": None}
        if next_max_count is None:
            return {"msg": "Max group count is required for mentor users", "data": None}

    role_changed = "role" in input_data and input_data["role"] != current_role
    before_user = fetch_user_by_id(user_id) if role_changed else None

    # Handle geography update. Country is the required half for non-admins; state
    # is sub-national and may always be cleared (most non-AU users have none).
    if "countryId" in input_data:
        if input_data["countryId"] is None:
            # The same two roles the create path exempts (see the geography
            # check in add_users_by_role). Adding "support" there and not here
            # left the client's own route broken in a way the create tests
            # could not see: an admin could make a support agent but could not
            # save one afterwards, and could not convert an existing account,
            # because adminweb sends countryId: null for every role without
            # geography and this returned "Country cannot be cleared".
            if next_role not in ROLES_WITHOUT_GEOGRAPHY:
                return {"msg": "Country cannot be cleared", "data": None}
            user.country_id = None
            user.state_id = None  # a state without its country is meaningless
        else:
            if not Countries.objects.filter(id=input_data["countryId"]).exists():
                return {"msg": f'Country "{input_data["countryId"]}" not found', "data": None}
            user.country_id = input_data["countryId"]

    country_cleared = "countryId" in input_data and input_data["countryId"] is None

    if "stateId" in input_data:
        if input_data["stateId"] is None:
            user.state_id = None
        elif country_cleared:
            # Same payload clears the country and sets a state — contradictory.
            # Reject rather than let the state quietly reinstate a country.
            return {"msg": "Cannot set a state while clearing the country", "data": None}
        else:
            state_obj = CountryStates.objects.filter(
                id=input_data["stateId"]
            ).select_related("country").first()
            if state_obj is None:
                return {"msg": f'State "{input_data["stateId"]}" not found', "data": None}
            if user.country_id and user.country_id != state_obj.country_id:
                return {"msg": "State does not belong to the selected country", "data": None}
            user.state_id = state_obj.id
            user.country_id = state_obj.country_id  # keep the pair coherent

    try:
        with transaction.atomic():
            # Update basic user fields
            if "firstName" in input_data:
                user.first_name = input_data["firstName"]
            if "lastName" in input_data:
                user.last_name = input_data["lastName"]
            if any(k in input_data for k in ["countryId", "stateId", "firstName", "lastName"]):
                user.save()
            
            # Handle role change
            if "role" in input_data and input_data["role"] != current_role:
                role_id = resolve_role_id(input_data["role"])
                
                # Invalidate current role
                RoleAssignmentHistory.objects.filter(
                    user_id=user_id
                ).filter(
                    Q(valid_to__isnull=True) | Q(valid_to__gte=now)
                ).update(valid_to=now)
                
                # Create new role assignment
                RoleAssignmentHistory.objects.create(
                    user_id=user_id,
                    role_id=role_id,
                    valid_from=now,
                    valid_to=None
                )
                user.is_staff = input_data["role"] == "admin"
                user.is_superuser = input_data["role"] == "admin"
                user.save(update_fields=["is_staff", "is_superuser"])
            
            # Update role-specific profiles
            if next_role == "student":
                upsert_student_profile(
                    user_id,
                    input_data.get("firstName", user.first_name),
                    input_data.get("lastName", user.last_name),
                    input_data.get("schoolName"),
                    input_data.get("yearLevel"),
                    supervisor_email=input_data["supervisorEmail"] if "supervisorEmail" in input_data else _UNSET,
                    state_id=user.state_id,
                    country_id=user.country_id,
                )
            elif user.roleassignmenthistory_set.filter(valid_to__isnull=False).exists():
                delete_student_details(user_id)
            
            if next_role == "supervisor":
                upsert_supervisor_profile(
                    user_id,
                    (input_data.get("supervisorSchoolName") or "").strip()
                )
            elif next_role != "supervisor":
                SupervisorProfile.objects.filter(user_id=user_id).delete()
            
            if next_role == "mentor":
                upsert_mentor_profile(
                    user_id,
                    background=input_data.get("mentorBackground"),
                    institution=input_data.get("mentorInstitution"),
                    mentor_reason=input_data.get("mentorReason"),
                    max_group_count=input_data.get("mentorMaxGroupCount")
                )
            elif next_role != "mentor":
                MentorProfile.objects.filter(user_id=user_id).delete()
            
            # Sync interests
            if next_role in ["student", "mentor"]:
                sync_user_interests(user_id, next_interests)
            else:
                delete_user_interests(user_id)
    
    except Exception as e:
        logger.exception("admin.user.update_failed user=%s", user_id)
        return {
            "msg": UNEXPECTED_FAILURE,
            "data": None
        }
    
    # Both permission markers below are decided from case-folded role names.
    # `resolve_role_id` reuses an existing row with `role_name__iexact`, so the
    # spelling stored in `roles` may be "Admin" or "Support" while adminweb
    # always sends lower case. A bare `==` then takes the wrong branch: with
    # "Admin" stored, saving an administrator's surname fell into the `else`
    # below and deleted their AdminScope row, dropping them out of the console.
    #
    # Only these two comparisons are folded. The rest of update_user still
    # compares role names case-sensitively, which is a separate, older defect
    # (a plain save can drop a SupervisorProfile) deliberately left for its own
    # change — it needs a data migration on the shared `roles` table.
    next_role_key = (next_role or "").strip().lower()
    current_role_key = (current_role or "").strip().lower()

    # Whether this save moved the account from one role to another, as opposed
    # to re-saving the role it already had. `role_changed` above compares the
    # raw strings, so it reads "Support" -> "support" as a change; this must
    # not, or a case mismatch alone would re-grant queue access.
    role_moved = "role" in input_data and next_role_key != current_role_key

    # Sync admin marker to the (possibly changed) role.
    if next_role_key == "admin":
        AdminScope.objects.get_or_create(user_id=user_id)
    else:
        AdminScope.objects.filter(user_id=user_id).delete()

    # Support access follows the role only when the role actually moved.
    #
    # Neither half may run on an ordinary save. This function runs on every
    # successful update, `next_role` falls back to the current role when the
    # caller sends none, and adminweb sends `role` on every save. Granting
    # unconditionally undid a deliberate revocation: an admin revoked queue
    # access on the roster page, someone corrected the person's surname, and
    # the row came back with no audit trail — the last support_scope event on
    # record stayed "delete" while the person still held access. Revoking
    # unconditionally is the mirror landmine: a mentor granted access from the
    # roster page would silently lose it on that same surname edit.
    #
    # `role_moved` is what separates the two. The roster page stays the place
    # to grant and revoke access for people whose role is something else; it is
    # also the only screen that first says how many unresolved tickets a
    # revocation would leave with nobody:
    # apps/tickets/views_admin.SupportScopeRevokeView.
    #
    # Both branches are audited, and the write and its audit row share one
    # transaction. Split across two, a crash between them leaves either queue
    # access nobody can account for or a record of a revocation that did not
    # happen; on a platform whose users are minors the first is the worse of
    # the two. tests/apps/tickets/test_api_admin.RosterAuditAtomicityTests
    # holds the roster page to the same rule.
    if role_moved and next_role_key == "support":
        with transaction.atomic():
            _, support_granted = SupportScope.objects.get_or_create(user_id=user_id)
            if support_granted:
                log_audit_event(
                    actor=initiated_by,
                    entity_type="support_scope",
                    entity_id=user_id,
                    action="create",
                    before_state=None,
                    after_state={"user_id": user_id, "via": "role_change"},
                )
    elif role_moved and current_role_key == "support":
        with transaction.atomic():
            removed, _ = SupportScope.objects.filter(user_id=user_id).delete()
            if removed:
                log_audit_event(
                    actor=initiated_by,
                    entity_type="support_scope",
                    entity_id=user_id,
                    action="delete",
                    before_state={"user_id": user_id},
                    after_state=None,
                )

    # Fetch updated user
    updated_user = fetch_user_by_id(user_id)
    if role_changed:
        log_audit_event(
            actor=initiated_by,
            entity_type="user",
            entity_id=user_id,
            action="role_change",
            before_state=before_user,
            after_state=updated_user,
        )
    return {"msg": "User updated successfully", "data": updated_user}


def update_status(user_id: int, is_active: bool, initiated_by=None) -> Dict[str, Any]:
    """
    Activate or deactivate a user account.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"msg": "User not found", "data": None}

    before_state = {"isActive": user.is_active, "accountStatus": user.account_status}
    user.is_active = is_active
    user.account_status = STATUS_ACTIVE if is_active else STATUS_DEACTIVATED
    user.save()
    log_audit_event(
        actor=initiated_by,
        entity_type="user",
        entity_id=user_id,
        action="status_change",
        before_state=before_state,
        after_state={"isActive": user.is_active, "accountStatus": user.account_status},
    )

    updated_user = fetch_user_by_id(user_id)
    status_text = "activated" if is_active else "deactivated"

    return {
        "msg": f"User {status_text} successfully",
        "data": updated_user
    }


def bulk_update_status(user_ids: List[int], is_active: bool, initiated_by=None) -> Dict[str, Any]:
    """
    Activate or deactivate multiple user accounts in one call.
    """
    try:
        ids = list(dict.fromkeys(int(uid) for uid in user_ids))
    except (TypeError, ValueError):
        return {"msg": "userIds must be a list of integer ids", "data": None}
    if not ids:
        return {"msg": "userIds must be a non-empty list", "data": None}

    # Guard against an admin sweeping their own account into a bulk deactivate
    skipped_self = False
    if not is_active and initiated_by is not None and initiated_by.id in ids:
        ids.remove(initiated_by.id)
        skipped_self = True

    users = User.objects.filter(id__in=ids)
    found_ids = {user.id for user in users}
    not_found_ids = [uid for uid in ids if uid not in found_ids]

    next_status = STATUS_ACTIVE if is_active else STATUS_DEACTIVATED
    updated_ids: List[int] = []
    unchanged_ids: List[int] = []
    with transaction.atomic():
        for user in users:
            if user.is_active == is_active and user.account_status == next_status:
                unchanged_ids.append(user.id)
                continue
            before_state = {"isActive": user.is_active, "accountStatus": user.account_status}
            user.is_active = is_active
            user.account_status = next_status
            user.save()
            log_audit_event(
                actor=initiated_by,
                entity_type="user",
                entity_id=user.id,
                action="status_change",
                before_state=before_state,
                after_state={"isActive": user.is_active, "accountStatus": user.account_status},
            )
            updated_ids.append(user.id)

    status_text = "activated" if is_active else "deactivated"
    msg_parts = [f"{len(updated_ids)} user(s) {status_text}"]
    if unchanged_ids:
        msg_parts.append(f"{len(unchanged_ids)} already {status_text}")
    if skipped_self:
        msg_parts.append("your own account was skipped")
    if not_found_ids:
        msg_parts.append(f"{len(not_found_ids)} not found")

    return {
        "msg": "; ".join(msg_parts),
        "data": {
            "updatedIds": updated_ids,
            "unchangedIds": unchanged_ids,
            "notFoundIds": not_found_ids,
            "skippedSelf": skipped_self,
        },
    }


def bulk_update_status_by_filter(filters: Dict[str, Any], is_active: bool,
                                 exclude_ids=None, initiated_by=None) -> Dict[str, Any]:
    """
    Activate or deactivate every user matching the given list filters
    ("select all matching"). Mirrors query_users' filter semantics so the action
    hits exactly the rows the admin was viewing; exclude_ids drops any rows they
    unchecked before confirming.
    """
    filters = filters or {}
    active_filter = filters.get("active")
    queryset = _build_user_filter_queryset(
        search=filters.get("search"),
        role=filters.get("role"),
        state=filters.get("state"),
        active=active_filter if isinstance(active_filter, bool) else None,
        in_group=filters.get("inGroup"),
        country=filters.get("country"),
    )
    ids = list(queryset.values_list("id", flat=True).distinct())

    if exclude_ids:
        try:
            excluded = {int(x) for x in exclude_ids}
        except (TypeError, ValueError):
            return {"msg": "excludeIds must be a list of integer ids", "data": None}
        ids = [uid for uid in ids if uid not in excluded]

    if not ids:
        return {
            "msg": "No matching users to update",
            "data": {
                "updatedIds": [],
                "unchangedIds": [],
                "notFoundIds": [],
                "skippedSelf": False,
            },
        }

    return bulk_update_status(ids, is_active, initiated_by=initiated_by)


def _purge_protecting_records(user_id: int) -> None:
    """Delete the record types that reference a user with on_delete=PROTECT,
    so a subsequent User delete succeeds instead of raising ProtectedError.

    Their children (message reactions/attachments, resource audiences, workshop
    attendance, match recommendations, ticket messages and attachments) all
    cascade, so no ordering is needed. The external blob store is intentionally
    left untouched — the app's normal resource/message deletion is a soft
    delete that never purges blobs either.
    """
    from apps.chat.models import Messages
    from apps.resources.models import Resources
    from apps.workshops.models import Workshops
    from apps.admin.models import MatchRun
    from apps.tickets.models import Ticket

    Messages.objects.filter(sender_user_id=user_id).delete()
    Resources.objects.filter(uploaded_by_id=user_id).delete()
    Workshops.objects.filter(host_user_id=user_id).delete()
    MatchRun.objects.filter(admin_user_id=user_id).delete()
    # Tickets the person raised, and with them every message and attachment on
    # those tickets. This is the same content chat.Messages is protected for:
    # free text a minor wrote about a problem, often carrying an address, a
    # phone number or a parent's email address. Their tickets used to survive
    # the account under no name, which made "delete this user" untrue for the
    # one store holding the most sensitive thing they ever typed.
    #
    # Only tickets they RAISED. Tickets merely assigned to them keep their
    # SET_NULL and stay in the queue: those belong to whoever asked for help,
    # and deleting an agent's account must not take a student's enquiry with
    # it. Support replies they wrote lose their author the same way and render
    # as "Support (account removed)".
    Ticket.objects.filter(created_by_id=user_id).delete()


def delete_user(user_id: int, initiated_by=None, force: bool = False) -> Dict[str, Any]:
    """
    Delete a user, and with force=True the content that protects them.

    Without force this refuses rather than cascading: anything referencing the
    user with on_delete=PROTECT stops the delete and the caller gets a message
    saying so.

    force=True purges those records first — see _purge_protecting_records for
    exactly which, and do not restate the list here. Two docstrings and three
    screens each kept their own copy of it, all five went stale together when
    tickets were added to the purge, and an admin was told four kinds of
    content would be destroyed while five were. The list the admin reads now
    lives in adminweb/src/components/people/ForceDeleteNotice.tsx, and this
    points at the code instead of paraphrasing it.

    Either way this permanently destroys content, so callers must gate force
    behind an explicit, confirmed admin action.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"msg": "User not found", "data": None}

    before_user = fetch_user_by_id(user_id)
    try:
        with transaction.atomic():
            log_audit_event(
                actor=initiated_by,
                entity_type="user",
                entity_id=user_id,
                action="force_delete" if force else "delete",
                before_state=before_user,
            )
            RoleAssignmentHistory.objects.filter(user_id=user_id).delete()
            UserInterest.objects.filter(user_id=user_id).delete()
            MentorProfile.objects.filter(user_id=user_id).delete()
            SupervisorProfile.objects.filter(user_id=user_id).delete()
            StudentProfile.objects.filter(user_id=user_id).delete()
            if force:
                _purge_protecting_records(user_id)
            User.objects.filter(id=user_id).delete()
    except ProtectedError:
        # Chat messages, uploaded resources, match runs, etc. reference the user
        # with on_delete=PROTECT. Fail cleanly (the atomic block rolls back) instead
        # of a 500 that would strand a bulk delete mid-loop. force=True purges these
        # first, so this path is only reached for a normal (non-force) delete.
        return {
            "msg": "User cannot be deleted because other records reference them",
            "data": None,
        }

    return {"msg": "User deleted successfully", "data": None}


def bulk_delete_users(user_ids: List[int], initiated_by=None,
                      force: bool = False) -> Dict[str, Any]:
    """
    Permanently delete multiple users in one call (hard delete).

    Dedupes ids and never deletes the initiator's own account. Each row is
    removed via delete_user, so every deletion is individually audit-logged.
    force=True also purges the records that PROTECT each user — see
    _purge_protecting_records for which, and delete_user for why this
    docstring no longer lists them.
    """
    try:
        ids = list(dict.fromkeys(int(uid) for uid in user_ids))
    except (TypeError, ValueError):
        return {"msg": "userIds must be a list of integer ids", "data": None}
    if not ids:
        return {"msg": "userIds must be a non-empty list", "data": None}

    skipped_self = False
    if initiated_by is not None and initiated_by.id in ids:
        ids.remove(initiated_by.id)
        skipped_self = True

    existing_ids = set(
        User.objects.filter(id__in=ids).values_list("id", flat=True)
    )
    deleted_ids: List[int] = []
    failed_ids: List[int] = []
    not_found_ids = [uid for uid in ids if uid not in existing_ids]
    for uid in ids:
        if uid not in existing_ids:
            continue
        # Each delete_user runs in its own transaction, so a protected/undeletable
        # user is reported in failed_ids rather than aborting the whole batch.
        if delete_user(uid, initiated_by=initiated_by, force=force).get("msg") == "User deleted successfully":
            deleted_ids.append(uid)
        else:
            failed_ids.append(uid)

    msg_parts = [f"{len(deleted_ids)} user(s) deleted"]
    if skipped_self:
        msg_parts.append("your own account was skipped")
    if failed_ids:
        msg_parts.append(f"{len(failed_ids)} could not be deleted (referenced by other records)")
    if not_found_ids:
        msg_parts.append(f"{len(not_found_ids)} not found")

    return {
        "msg": "; ".join(msg_parts),
        "data": {
            "deletedIds": deleted_ids,
            "failedIds": failed_ids,
            "notFoundIds": not_found_ids,
            "skippedSelf": skipped_self,
        },
    }


def _empty_delete_result(msg: str, skipped_admins: int = 0) -> Dict[str, Any]:
    return {
        "msg": msg,
        "data": {
            "deletedIds": [], "failedIds": [], "notFoundIds": [],
            "skippedSelf": False, "skippedAdmins": skipped_admins,
        },
    }


def bulk_delete_users_by_filter(filters: Dict[str, Any], exclude_ids=None,
                                initiated_by=None, expected_count=None,
                                force: bool = False) -> Dict[str, Any]:
    """
    Permanently delete every user matching the given list filters
    ("select all matching"). Mirrors query_users' filter semantics so the action
    hits exactly the rows the admin was viewing; exclude_ids drops any rows they
    unchecked before confirming.

    Safeguards for this mass-destructive path:
    - admin accounts are never mass-deleted (only the individual delete can),
    - the initiator's own account is skipped,
    - expected_count guards against the set growing between preview and confirm
      (users created in that window are not silently swept into a hard delete).
    """
    filters = filters or {}
    active_filter = filters.get("active")
    queryset = _build_user_filter_queryset(
        search=filters.get("search"),
        role=filters.get("role"),
        state=filters.get("state"),
        active=active_filter if isinstance(active_filter, bool) else None,
        in_group=filters.get("inGroup"),
        country=filters.get("country"),
    )
    ids = list(queryset.values_list("id", flat=True).distinct())

    if exclude_ids:
        try:
            excluded = {int(x) for x in exclude_ids}
        except (TypeError, ValueError):
            return {"msg": "excludeIds must be a list of integer ids", "data": None}
        ids = [uid for uid in ids if uid not in excluded]

    # Refuse if the live set grew beyond what the admin reviewed — a hard delete
    # must not reach rows created after the count was shown.
    if expected_count is not None:
        try:
            expected = int(expected_count)
        except (TypeError, ValueError):
            expected = None
        if expected is not None and len(ids) > expected:
            return {
                "msg": (
                    f"The matching set changed (now {len(ids)}, was {expected}). "
                    "Refresh and re-review before deleting."
                ),
                "data": None,
            }

    if not ids:
        return _empty_delete_result("No matching users to delete")

    # Never mass-delete admin accounts (other admins would otherwise be swept in).
    admin_ids = set(
        AdminScope.objects.filter(user_id__in=ids).values_list("user_id", flat=True)
    )
    skipped_admins = len(admin_ids)
    if admin_ids:
        ids = [uid for uid in ids if uid not in admin_ids]
    if not ids:
        return _empty_delete_result(
            "No deletable users (admin accounts are protected)", skipped_admins
        )

    result = bulk_delete_users(ids, initiated_by=initiated_by, force=force)
    if result.get("data") is not None and skipped_admins:
        result["data"]["skippedAdmins"] = skipped_admins
        result["msg"] += f"; {skipped_admins} admin account(s) skipped"
    return result


def has_ungrouped_students() -> bool:
    """
    Check if there are any students without an active group membership.
    """
    from django.db.models import Exists, OuterRef
    from apps.groups.models import GroupMembership

    active_membership_subquery = GroupMembership.objects.filter(
        user_id=OuterRef('user_id'),
        left_at__isnull=True
    )
    return StudentProfile.objects.filter(~Exists(active_membership_subquery)).exists()
