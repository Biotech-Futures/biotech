"""
TypeScript User Module Conversion to Python
Literal translation from admin/apps/server/src/module/user/
"""
from django.db import transaction
from django.utils import timezone
from django.db.models import Exists, OuterRef, Q
from typing import List, Dict, Any, Optional

# Import models
from apps.users.models import (
    User, StudentProfile, SupervisorProfile, MentorProfile,
    AreasOfInterest, UserInterest
)
from apps.users.models.admin_scope import AdminScope
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Groups, GroupMembership
from apps.admin.scope_utils import get_admin_track_ids


# ============================================================================
# CONSTANTS
# ============================================================================
ROLES = ["student", "mentor", "supervisor", "admin"]

_UNSET = object()  # sentinel: "not provided" vs explicit None/empty
STATUS_INVITED = "invited"
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_DEACTIVATED = "deactivated"

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


def upsert_student_profile(
    user_id: int,
    first_name: str,
    last_name: str,
    school_name: Optional[str],
    year_level: Optional[int],
    join_permission_received: Optional[bool],
    supervisor_email: Any = _UNSET,
) -> None:
    """
    Create or update student profile.
    supervisor_email=_UNSET means don't touch the existing supervisor link.
    supervisor_email=None or "" clears the supervisor link.
    supervisor_email="email@..." looks up the supervisor and sets the link.
    """
    profile_data = {
        "pg_first_name": first_name,
        "pg_last_name": last_name,
        "parent_guardian_flag": True,
        "school_name": (school_name or "").strip(),
        "year_lvl": str(year_level or ""),
        "has_join_permission": join_permission_received or False,
        "joinperm_responseID": None,
    }

    if supervisor_email is not _UNSET:
        resolved_id = None
        if supervisor_email:
            sup_user = User.objects.filter(email__iexact=supervisor_email.strip()).first()
            if sup_user:
                sup_profile = SupervisorProfile.objects.filter(user_id=sup_user.id).first()
                if sup_profile:
                    resolved_id = sup_profile.user_id
        profile_data["supervisor_id"] = resolved_id

    StudentProfile.objects.update_or_create(
        user_id=user_id,
        defaults=profile_data
    )


def upsert_supervisor_profile(user_id: int, school_name: str) -> None:
    """
    Create or update supervisor profile.
    """
    SupervisorProfile.objects.update_or_create(
        user_id=user_id,
        defaults={"school_name": school_name}
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


def build_user_dict(user: User, role_str: Optional[str] = None,
                   track_name: Optional[str] = None,
                   group_name: Optional[str] = None,
                   student_profile: Optional[StudentProfile] = None,
                   supervisor_profile: Optional[SupervisorProfile] = None,
                   mentor_profile: Optional[MentorProfile] = None,
                   admin_tracks: Optional[List[str]] = None,
                   admin_is_global: bool = False,
                   supervisor_name: Optional[str] = None,
                   supervisor_email_val: Optional[str] = None,
                   supervisees: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Build a user dictionary with all related data.
    """
    # Get current role if not provided
    if role_str is None:
        current_role = RoleAssignmentHistory.objects.filter(
            user_id=user.id,
            valid_to__isnull=True
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
        "track": track_name,
        "groupName": group_name,
        "schoolName": school_name,
        "mentorBackground": mentor_profile.background if mentor_profile else None,
        "mentorInstitution": mentor_profile.institution if mentor_profile else None,
        "mentorReason": mentor_profile.mentor_reason if mentor_profile else None,
        "mentorMaxGroupCount": mentor_profile.max_group_count if mentor_profile else None,
        "yearLevel": int(student_profile.year_lvl) if student_profile and student_profile.year_lvl else None,
        "joinPermissionReceived": student_profile.has_join_permission if student_profile else False,
        "interests": interests,
        "adminTracks": admin_tracks,
        "adminIsGlobal": admin_is_global,
        "isActive": user.is_active,
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
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

    student_profile = StudentProfile.objects.filter(user_id=user_id).first()
    supervisor_profile = SupervisorProfile.objects.filter(user_id=user_id).first()
    mentor_profile = MentorProfile.objects.filter(user_id=user_id).first()
    admin_scope = get_admin_scope_summary(user_id)

    track_name = user.track.track_name if user.track else None

    # Resolve current role so we can fetch the right extra data
    current_role_obj = RoleAssignmentHistory.objects.filter(
        user_id=user_id, valid_to__isnull=True
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
        track_name=track_name,
        student_profile=student_profile,
        supervisor_profile=supervisor_profile,
        mentor_profile=mentor_profile,
        admin_tracks=admin_scope["tracks"],
        admin_is_global=admin_scope["is_global"],
        supervisor_name=supervisor_name,
        supervisor_email_val=supervisor_email_val,
        supervisees=supervisees,
    )


def get_admin_scope_summary(user_id: int) -> Dict[str, Any]:
    return get_admin_scope_summaries_by_user_ids([user_id]).get(
        user_id,
        {"tracks": None, "is_global": False},
    )


def get_admin_scope_summaries_by_user_ids(user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not user_ids:
        return {}

    admin_scope_by_user: Dict[int, Dict[str, Any]] = {}
    global_user_ids = set()

    for scope in (
        AdminScope.objects.filter(user_id__in=user_ids)
        .select_related("track")
        .order_by("track__track_name")
    ):
        if scope.is_global:
            global_user_ids.add(scope.user_id)
            continue
        if scope.track:
            admin_scope = admin_scope_by_user.setdefault(
                scope.user_id,
                {"tracks": [], "is_global": False},
            )
            admin_scope["tracks"].append(scope.track.track_name)

    if global_user_ids:
        all_track_names = list(
            Tracks.objects.order_by("track_name").values_list("track_name", flat=True)
        )
        for user_id in global_user_ids:
            admin_scope_by_user[user_id] = {
                "tracks": all_track_names,
                "is_global": True,
            }

    return admin_scope_by_user


# ============================================================================
# QUERY FUNCTIONS (query.ts logic)
# ============================================================================

def query_users(page: int = 1, limit: int = 10, search: Optional[str] = None,
               role: Optional[str] = None, track: Optional[str] = None,
               active: Optional[bool] = None, in_group: Optional[str] = None,
               sort_by: str = "createdAt", sort_order: str = "desc",
               requesting_user=None) -> Dict[str, Any]:
    """
    Query users with pagination and filters.
    """
    offset = (page - 1) * limit

    # Build filter conditions
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
        filters &= Q(roleassignmenthistory__role__role_name=role,
                     roleassignmenthistory__valid_to__isnull=True)

    if track:
        filters &= Q(track__track_name=track)

    if active is not None:
        filters &= Q(is_active=active)

    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        filters &= (Q(track_id__in=track_ids) | Q(track__isnull=True))

    queryset = _filter_by_active_group_membership(
        User.objects.filter(filters),
        in_group,
    )

    # Get total count
    total = queryset.values('id').distinct().count()

    # Determine sort order
    order_by = []
    if sort_by == "name":
        order_by = ["first_name", "last_name", "id"]
    else:  # createdAt
        order_by = ["date_joined", "id"]

    if sort_order == "desc":
        order_by = [f"-{field}" if field != "id" else field for field in order_by]

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
        u.id: u for u in User.objects.filter(id__in=user_ids).select_related('track')
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
    admin_scope_map = get_admin_scope_summaries_by_user_ids(user_ids)

    # Active role assignments
    role_map = {}
    for rah in RoleAssignmentHistory.objects.filter(
        user_id__in=user_ids, valid_to__isnull=True
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
        admin_scope = admin_scope_map.get(uid, {"tracks": None, "is_global": False})
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
            "track": user.track.track_name if user.track else None,
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
            "adminTracks": admin_scope["tracks"],
            "adminIsGlobal": admin_scope["is_global"],
            "isActive": user.is_active,
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


def query_tracks(requesting_user=None) -> Dict[str, Any]:
    """
    Get all available tracks for filtering and assignment.
    """
    qs = Tracks.objects.all()
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        qs = qs.filter(id__in=track_ids)
    tracks_list = qs.values('id', 'track_name').order_by('track_name')
    items = [
        {"id": track["id"], "trackName": track["track_name"]}
        for track in tracks_list
    ]
    return {"msg": "Tracks retrieved successfully", "data": items}


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
# STUDENT QUERY FUNCTIONS (student.ts logic)
# ============================================================================

def query_students(page: int = 1, limit: int = 10, search: Optional[str] = None,
                  year_level: Optional[int] = None, track: Optional[str] = None,
                  interest: Optional[str] = None, in_group: Optional[str] = None,
                  active: Optional[bool] = None) -> Dict[str, Any]:
    """
    Query students with student-specific filters.
    """
    offset = (page - 1) * limit
    
    # Base query: only students
    filters = Q(roleassignmenthistory__role__role_name='student',
               roleassignmenthistory__valid_to__isnull=True)
    
    if search:
        filters &= (
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    if year_level:
        filters &= Q(studentprofile__year_lvl=str(year_level))
    
    if track:
        filters &= Q(track__track_name=track)
    
    if active is not None:
        filters &= Q(is_active=active)
    
    if interest:
        filters &= Q(
            userinterest__interest__interest_desc__icontains=interest
        )
    
    queryset = _filter_by_active_group_membership(
        User.objects.filter(filters),
        in_group,
    )
    
    # Get total count
    total = queryset.values('id').distinct().count()
    
    # Get paginated user IDs
    user_ids = (
        queryset
        .values_list('id', flat=True)
        .distinct()
        .order_by('last_name', 'first_name', 'id')[offset:offset + limit]
    )
    
    if not user_ids:
        return {
            "msg": "Students retrieved successfully",
            "data": {
                "items": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "hasMore": False,
            }
        }
    
    # Fetch detailed student data
    students_list = []
    for user_id in user_ids:
        user = User.objects.get(id=user_id)
        student_profile = StudentProfile.objects.get(user_id=user_id)
        
        # Get group
        group_name = None
        group_id = None
        group_membership = GroupMembership.objects.filter(
            user_id=user_id,
            left_at__isnull=True
        ).select_related('group').first()
        
        if group_membership and not group_membership.group.deleted_at:
            group_name = group_membership.group.group_name
            group_id = group_membership.group.id
        
        # Get interests
        interests = [
            {
                "id": ui.interest_id,
                "description": ui.interest.interest_desc
            }
            for ui in UserInterest.objects.filter(user_id=user_id).select_related('interest')
        ]
        
        student_item = {
            "id": user.id,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "email": user.email,
            "role": "student",
            "track": user.track.track_name if user.track else None,
            "isActive": user.is_active,
            "accountStatus": "active" if user.is_active else "deactivated",
            "schoolName": student_profile.school_name,
            "yearLevel": int(student_profile.year_lvl) if student_profile.year_lvl else None,
            "hasJoinPermission": student_profile.has_join_permission,
            "joinpermResponseId": student_profile.joinperm_responseID,
            "groupId": group_id,
            "groupName": group_name,
            "interests": interests,
        }
        students_list.append(student_item)
    
    return {
        "msg": "Students retrieved successfully",
        "data": {
            "items": students_list,
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": offset + len(students_list) < total,
        }
    }


# ============================================================================
# MUTATION FUNCTIONS (mutation.ts logic)
# ============================================================================

def add_users_by_role(inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Bulk create users with validation and role-specific setup.
    """
    results = []
    now = timezone.now()
    
    for input_data in inputs:
        email = input_data.get("email", "").lower().strip()
        first_name = input_data.get("firstName", "")
        last_name = input_data.get("lastName", "")
        role = input_data.get("role", "student")
        track_name = (input_data.get("track") or "").strip()
        
        # Check if user exists
        if User.objects.filter(email=email).exists():
            results.append({
                "input": input_data,
                "msg": "Email already exists",
                "data": None
            })
            continue
        
        # Validate track for non-admin users
        if role != "admin" and not track_name:
            results.append({
                "input": input_data,
                "msg": "Track is required",
                "data": None
            })
            continue
        
        # Validate admin tracks
        if role == "admin":
            admin_is_global = bool(input_data.get("adminIsGlobal"))
            admin_tracks = [
                t.strip() for t in (input_data.get("adminTracks") or [])
                if t.strip()
            ]
            if not admin_is_global and not admin_tracks:
                results.append({
                    "input": input_data,
                    "msg": "Select global admin or at least one admin track for admin users",
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
        
        # Resolve track ID
        track_id = None
        if track_name:
            try:
                track = Tracks.objects.get(track_name=track_name)
                track_id = track.id
            except Tracks.DoesNotExist:
                results.append({
                    "input": input_data,
                    "msg": f'Track "{track_name}" not found',
                    "data": None
                })
                continue
        
        # Resolve role ID
        try:
            role_id = resolve_role_id(role)
        except Exception as e:
            results.append({
                "input": input_data,
                "msg": f"Error resolving role: {str(e)}",
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
                    track_id=track_id,
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
                        input_data.get("joinPermissionReceived"),
                        supervisor_email=input_data.get("supervisorEmail") or _UNSET,
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
            results.append({
                "input": input_data,
                "msg": f"Failed to create user: {str(e)}",
                "data": None
            })
            continue
        
        # Create AdminScope rows for admin users
        if role == "admin":
            try:
                admin_is_global = bool(input_data.get("adminIsGlobal"))
                normalized_tracks = [
                    t.strip() for t in (input_data.get("adminTracks") or []) if t.strip()
                ]
                if admin_is_global:
                    AdminScope.objects.get_or_create(
                        user_id=new_user_id,
                        is_global=True,
                        defaults={"track": None},
                    )
                else:
                    for track_name in normalized_tracks:
                        try:
                            track_obj = Tracks.objects.get(track_name=track_name)
                            AdminScope.objects.get_or_create(
                                user_id=new_user_id,
                                track=track_obj,
                                defaults={"is_global": False},
                            )
                        except Tracks.DoesNotExist:
                            pass
            except Exception as e:
                rollback_created_user(new_user_id)
                results.append({
                    "input": input_data,
                    "msg": f"Unable to create admin scope: {str(e)}",
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


def create_user(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a single user.
    """
    results = add_users_by_role([input_data])
    result = results[0]
    return {"msg": result["msg"], "data": result["data"]}


def bulk_create_users(users_input: List[Dict[str, Any]], admin_user_id: str) -> Dict[str, Any]:
    """
    Bulk create users from list.
    """
    created = []
    skipped = []

    results = add_users_by_role(users_input)

    for result in results:
        if result["data"]:
            created.append(result["data"])
        else:
            skipped.append(result["input"].get("email", "unknown"))

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

    return {
        "msg": f"Bulk import complete: {len(created)} created, {len(skipped)} skipped",
        "data": {
            "created": created,
            "skipped": skipped
        }
    }


def update_user(user_id: int, input_data: Dict[str, Any]) -> Dict[str, Any]:
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
            user_id=user_id, valid_to__isnull=True
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

    if next_role == "admin":
        current_admin_scope = get_admin_scope_summary(user_id)
        next_admin_is_global = bool(
            input_data.get("adminIsGlobal", current_admin_scope["is_global"])
        )
        next_admin_tracks = input_data.get("adminTracks")
        if next_admin_tracks is None:
            next_admin_tracks = current_admin_scope["tracks"] or []
        next_admin_tracks = [track.strip() for track in next_admin_tracks if track.strip()]

        if not next_admin_is_global and not next_admin_tracks:
            return {
                "msg": "Select global admin or at least one admin track for admin users",
                "data": None,
            }
    
    # Handle track update
    if "track" in input_data:
        if next_role == "admin":
            if input_data["track"] is None:
                user.track_id = None
        else:
            if input_data["track"] is None:
                return {"msg": "Track cannot be cleared", "data": None}
            
            try:
                track = Tracks.objects.get(track_name=input_data["track"])
                user.track_id = track.id
            except Tracks.DoesNotExist:
                return {"msg": f'Track "{input_data["track"]}" not found', "data": None}
    
    try:
        with transaction.atomic():
            # Update basic user fields
            if "firstName" in input_data:
                user.first_name = input_data["firstName"]
            if "lastName" in input_data:
                user.last_name = input_data["lastName"]
            if "track" in input_data or any(k in input_data for k in ["firstName", "lastName"]):
                user.save()
            
            # Handle role change
            if "role" in input_data and input_data["role"] != current_role:
                role_id = resolve_role_id(input_data["role"])
                
                # Invalidate current role
                RoleAssignmentHistory.objects.filter(
                    user_id=user_id,
                    valid_to__isnull=True
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
                    input_data.get("joinPermissionReceived"),
                    supervisor_email=input_data["supervisorEmail"] if "supervisorEmail" in input_data else _UNSET,
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
        return {
            "msg": f"Unable to update user: {str(e)}",
            "data": None
        }
    
    # Update admin scopes if needed
    if ("adminTracks" in input_data or "adminIsGlobal" in input_data) and next_role == "admin":
        admin_is_global = bool(input_data.get("adminIsGlobal", False))
        normalized_tracks = [
            t.strip() for t in (input_data.get("adminTracks") or []) if t.strip()
        ]
        AdminScope.objects.filter(user_id=user_id).delete()
        if admin_is_global:
            AdminScope.objects.get_or_create(
                user_id=user_id,
                is_global=True,
                defaults={"track": None},
            )
        else:
            for track_name in normalized_tracks:
                try:
                    track_obj = Tracks.objects.get(track_name=track_name)
                    AdminScope.objects.get_or_create(
                        user_id=user_id,
                        track=track_obj,
                        defaults={"is_global": False},
                    )
                except Tracks.DoesNotExist:
                    pass
    elif next_role != "admin":
        AdminScope.objects.filter(user_id=user_id).delete()
    
    # Fetch updated user
    updated_user = fetch_user_by_id(user_id)
    return {"msg": "User updated successfully", "data": updated_user}


def update_status(user_id: int, is_active: bool) -> Dict[str, Any]:
    """
    Activate or deactivate a user account.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"msg": "User not found", "data": None}
    
    user.is_active = is_active
    user.account_status = STATUS_ACTIVE if is_active else STATUS_DEACTIVATED
    user.save()
    
    updated_user = fetch_user_by_id(user_id)
    status_text = "activated" if is_active else "deactivated"
    
    return {
        "msg": f"User {status_text} successfully",
        "data": updated_user
    }


def delete_user(user_id: int) -> Dict[str, Any]:
    """
    Delete a user and all related data.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"msg": "User not found", "data": None}

    with transaction.atomic():
        RoleAssignmentHistory.objects.filter(user_id=user_id).delete()
        UserInterest.objects.filter(user_id=user_id).delete()
        MentorProfile.objects.filter(user_id=user_id).delete()
        SupervisorProfile.objects.filter(user_id=user_id).delete()
        StudentProfile.objects.filter(user_id=user_id).delete()
        User.objects.filter(id=user_id).delete()

    return {"msg": "User deleted successfully", "data": None}


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
