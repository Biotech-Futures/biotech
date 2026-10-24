"""
Admin User Views Service
Powers the /api/v1/admin/view/ endpoints:
- View Query Compilation Engine (Role, Status, Engagement, Case-Insensitive Q)
- Dynamic User View Execution (pagination, search, sorting)
- Streaming CSV Export adhering strictly to visible_columns
"""

import csv
import io
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.db.models import Count, Exists, F, Min, OuterRef, Q
from django.http import HttpResponse
from django.utils import timezone

from apps.admin.models import AdminView
from apps.admin.services.user import (
    _user_country_dict,
    _user_state_dict,
    get_admin_user_ids,
)
from apps.groups.models import GroupMembership, Groups, group_name_sort_key
from apps.grading.services.text import natural_key
from apps.resources.models import RoleAssignmentHistory
from apps.submissions.services import current_cohort
from apps.users.returning import earlier_challenge_year
from apps.users.models import (
    MentorProfile,
    StudentProfile,
    SupervisorProfile,
    User,
    UserInterest,
)
from apps.users.models.admin_scope import AdminScope


# ============================================================================
# COLUMN HEADERS MAP FOR CSV EXPORT
# ============================================================================
COLUMN_HEADER_MAP: Dict[str, str] = {
    "name": "Full Name",
    "full_name": "Full Name",
    "email": "Email",
    "role": "Role",
    "school": "School / Institution",
    "institution": "School / Institution",
    "school_name": "School / Institution",
    "matched_mentor": "Matched Mentor / Mentee",
    "matched_partner": "Matched Mentor / Mentee",
    "status": "Status",
    "phone": "Phone",
    "state": "State",
    "country": "Country",
    "interests": "Interests",
    "interest": "Interests",
    "lastLogin": "Last Login",
    "last_login": "Last Login",
    "lastlogin": "Last Login",
    "yearLevel": "Year Level",
    "year_level": "Year Level",
    "year_lvl": "Year Level",
    "yearlevel": "Year Level",
    "group": "Group",
    "group_count": "Number of Groups",
    "groupCount": "Number of Groups",
    "groupcount": "Number of Groups",
    "number_of_groups": "Number of Groups",
    "group_number": "Group Number",
    "groupNumber": "Group Number",
    "groupnumber": "Group Number",
    "pronouns": "Pronouns",
    "mentor_group_capacity": "Group Capacity",
    "group_capacity": "Group Capacity",
    "mentor_capacity": "Group Capacity",
    "max_group_count": "Group Capacity",
    "mentor_background": "Mentor Background",
    "mentor_year_of_study": "Mentor Year of Study",
    "mentor_field_of_study": "Mentor Field of Study",
    "supervisor_email": "Supervisor Email",
    "guardian_email": "Guardian Email",
    "guardian_permission": "Guardian Permission",
}


# The mentor background choices as they read ("University Student – Postgraduate"),
# so a table of mentors says what they are rather than the stored code.
MENTOR_BACKGROUND_LABELS: Dict[str, str] = dict(MentorProfile.BackgroundChoices.choices)


def mentor_background_label(background: Optional[str]) -> Optional[str]:
    """A mentor's background as it reads; a value typed before the choices
    existed stays as it was written."""
    if not background:
        return None
    return MENTOR_BACKGROUND_LABELS.get(background, background)


# ============================================================================
# QUERY BUILDER ENGINE
# ============================================================================

def build_view_queryset(
    criteria: Dict[str, Any],
    search: Optional[str] = None,
    sort_by: str = "createdAt",
    sort_order: str = "desc",
) -> Tuple[Any, List[str]]:
    """
    Compiles filter criteria into a Django QuerySet of User.
    Returns (queryset, order_by_fields).
    """
    now = timezone.now()
    filters = Q()

    # 1. Search filter
    if search:
        s = search.strip()
        filters &= (
            Q(first_name__icontains=s)
            | Q(last_name__icontains=s)
            | Q(email__icontains=s)
            | Q(groupmembership__group__group_name__icontains=s)
        )

    # 2. Target Roles filter
    target_roles = criteria.get("target_roles") or []
    if target_roles and "all" not in target_roles:
        normalized_roles = [str(r).lower().strip() for r in target_roles if str(r).strip()]
        has_admin = "admin" in normalized_roles
        other_roles = [r for r in normalized_roles if r != "admin"]

        role_q = Q()
        if other_roles:
            role_q |= Q(
                roleassignmenthistory__role__role_name__in=other_roles,
                roleassignmenthistory__valid_to__isnull=True,
            ) | Q(
                roleassignmenthistory__role__role_name__in=other_roles,
                roleassignmenthistory__valid_to__gte=now,
            )

        if has_admin:
            admin_user_ids = AdminScope.objects.values_list("user_id", flat=True)
            role_q |= Q(id__in=admin_user_ids)

        if role_q:
            filters &= role_q

    # 3. Account Status filter
    account_status = str(criteria.get("account_status", "all")).lower().strip()
    if account_status == "active":
        filters &= Q(is_active=True)
    elif account_status == "inactive":
        filters &= Q(is_active=False)

    # 4. Engagement / Matching Status filter
    engagement_status = str(criteria.get("engagement_status", "all")).lower().strip()
    active_membership = GroupMembership.objects.filter(
        user=OuterRef("pk"),
        left_at__isnull=True,
        group__deleted_at__isnull=True,
    )
    if engagement_status == "matched":
        filters &= Exists(active_membership)
    elif engagement_status == "unmatched":
        filters &= ~Exists(active_membership)
    elif engagement_status == "pending":
        filters &= Q(account_status__in=["pending", "invited"]) | (
            ~Exists(active_membership) & Q(is_active=True)
        )

    # 5. Advanced Conditions
    conditions = criteria.get("advanced_conditions") or []
    if conditions:
        composite_condition: Optional[Q] = None

        for cond in conditions:
            field = str(cond.get("field", "")).strip()
            operator = str(cond.get("operator", "equals")).strip().lower()
            val = str(cond.get("value", "")).strip()
            logic = str(cond.get("logic", "AND")).strip().upper()

            cond_q = _build_single_condition_q(field, operator, val)
            if cond_q is None:
                continue

            if composite_condition is None:
                composite_condition = cond_q
            elif logic == "OR":
                composite_condition = composite_condition | cond_q
            else:
                composite_condition = composite_condition & cond_q

        if composite_condition is not None:
            filters &= composite_condition

    # Sorting
    sort_map = {
        "name": ["first_name", "last_name", "id"],
        "email": ["email", "id"],
        "role": ["roleassignmenthistory__role__role_name", "first_name", "last_name", "id"],
        "country": ["country__country_name", "first_name", "last_name", "id"],
        "state": ["state__state_name", "first_name", "last_name", "id"],
        "status": ["is_active", "first_name", "last_name", "id"],
        "school": ["studentprofile__school_name", "first_name", "last_name", "id"],
        "yearLevel": ["studentprofile__year_lvl", "first_name", "last_name", "id"],
        "group": ["group_name_key", "first_name", "last_name", "id"],
        "groupCount": ["active_group_count", "first_name", "last_name", "id"],
        "group_count": ["active_group_count", "first_name", "last_name", "id"],
        "groupNumber": ["group_number_key", "first_name", "last_name", "id"],
        "group_number": ["group_number_key", "first_name", "last_name", "id"],
        "createdAt": ["date_joined", "id"],
        "lastLogin": ["last_login", "first_name", "last_name", "id"],
    }
    order_by = sort_map.get(sort_by, sort_map["createdAt"])
    if sort_order == "desc":
        order_by = [f"-{f}" if f != "id" else f for f in order_by]

    qs = User.objects.filter(filters)
    if sort_by == "group":
        qs = qs.annotate(
            group_name_key=group_name_sort_key("groupmembership__group__group_name")
        )
    elif sort_by in ("groupCount", "group_count"):
        qs = qs.annotate(
            active_group_count=Count(
                "groupmembership__group",
                filter=Q(
                    groupmembership__left_at__isnull=True,
                    groupmembership__group__deleted_at__isnull=True,
                ),
                distinct=True,
            )
        )
    elif sort_by in ("groupNumber", "group_number"):
        # One row per user: the aggregate collapses a user's memberships to
        # their lowest group number. Annotating the padded group name directly
        # would instead multiply the user across their memberships, so the
        # table would list them once per group.
        qs = qs.annotate(
            group_number_key=Min(
                group_name_sort_key("groupmembership__group__group_name"),
                filter=Q(
                    groupmembership__left_at__isnull=True,
                    groupmembership__group__deleted_at__isnull=True,
                ),
            )
        )

    return qs, order_by


def _build_single_condition_q(field: str, operator: str, val: str) -> Optional[Q]:
    """
    Builds a single Q object for an attribute condition row.
    Text matching is case-insensitive.
    """
    field_lower = field.lower()

    # Determine database lookup path
    if field_lower in ("program", "group"):
        lookup = "groupmembership__group__group_name"
    elif field_lower == "country":
        lookup = "country__country_name"
    elif field_lower == "state":
        lookup = "state__state_name"
    elif field_lower in ("school", "institution", "school / institution"):
        # Multi-profile field: student school, supervisor school, mentor institution
        return _build_multi_field_q(
            ["studentprofile__school_name", "supervisorprofile__school_name", "mentorprofile__institution"],
            operator,
            val
        )
    elif field_lower in ("yearlevel", "year_lvl", "year level"):
        lookup = "studentprofile__year_lvl"
    elif field_lower in ("interest", "interests"):
        lookup = "userinterest__interest__interest_desc"
    elif field_lower == "email":
        lookup = "email"
    elif field_lower == "role":
        now = timezone.now()
        if operator in ("equals", "iexact"):
            if val.lower() == "admin":
                return Q(id__in=AdminScope.objects.values_list("user_id", flat=True))
            return Q(
                roleassignmenthistory__role__role_name__iexact=val,
                roleassignmenthistory__valid_to__isnull=True,
            ) | Q(
                roleassignmenthistory__role__role_name__iexact=val,
                roleassignmenthistory__valid_to__gte=now,
            )
        elif operator in ("not equals", "not_equals"):
            if val.lower() == "admin":
                return ~Q(id__in=AdminScope.objects.values_list("user_id", flat=True))
            return ~Q(
                roleassignmenthistory__role__role_name__iexact=val,
                roleassignmenthistory__valid_to__isnull=True,
            ) & ~Q(
                roleassignmenthistory__role__role_name__iexact=val,
                roleassignmenthistory__valid_to__gte=now,
            )
        lookup = "roleassignmenthistory__role__role_name"
    else:
        # Fallback to direct user model attribute or ignore
        if hasattr(User, field):
            lookup = field
        else:
            return None

    # Apply operator
    if operator in ("equals", "iexact"):
        return Q(**{f"{lookup}__iexact": val})
    elif operator in ("not equals", "not_equals"):
        return ~Q(**{f"{lookup}__iexact": val})
    elif operator in ("contains", "icontains"):
        return Q(**{f"{lookup}__icontains": val})
    elif operator in ("is empty", "is_empty"):
        return Q(**{f"{lookup}__isnull": True}) | Q(**{f"{lookup}__exact": ""})
    elif operator in ("is set", "is_set"):
        return Q(**{f"{lookup}__isnull": False}) & ~Q(**{f"{lookup}__exact": ""})

    return None


def _build_multi_field_q(lookups: List[str], operator: str, val: str) -> Q:
    """Helper to evaluate an operator across multiple alternative fields with OR."""
    res = Q()
    for lk in lookups:
        if operator in ("equals", "iexact"):
            res |= Q(**{f"{lk}__iexact": val})
        elif operator in ("not equals", "not_equals"):
            res |= ~Q(**{f"{lk}__iexact": val})
        elif operator in ("contains", "icontains"):
            res |= Q(**{f"{lk}__icontains": val})
        elif operator in ("is empty", "is_empty"):
            res |= Q(**{f"{lk}__isnull": True}) | Q(**{f"{lk}__exact": ""})
        elif operator in ("is set", "is_set"):
            res |= Q(**{f"{lk}__isnull": False}) & ~Q(**{f"{lk}__exact": ""})
    return res


# ============================================================================
# EXECUTION & DATA RETRIEVAL
# ============================================================================

def execute_view_query(
    view: AdminView,
    page: int = 1,
    limit: int = 25,
    search: Optional[str] = None,
    sort_by: str = "createdAt",
    sort_order: str = "desc",
) -> Dict[str, Any]:
    """
    Executes an AdminView query with pagination and returns serialized users.
    """
    criteria = {
        "target_roles": view.target_roles,
        "account_status": view.account_status,
        "engagement_status": view.engagement_status,
        "advanced_conditions": view.advanced_conditions,
    }

    qs, order_by = build_view_queryset(
        criteria=criteria,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total = qs.values("id").distinct().count()
    offset = (page - 1) * limit

    user_ids = list(
        qs.values_list("id", flat=True)
        .distinct()
        .order_by(*order_by)[offset:offset + limit]
    )

    # Touch last_run_at
    view.last_run_at = timezone.now()
    view.save(update_fields=["last_run_at"])

    if not user_ids:
        return {
            "items": [],
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": False,
            "view": serialize_admin_view(view),
        }

    users_list = _hydrate_users_by_ids(user_ids)

    return {
        "items": users_list,
        "total": total,
        "page": page,
        "limit": limit,
        "hasMore": offset + len(users_list) < total,
        "view": serialize_admin_view(view),
    }


def _hydrate_users_by_ids(user_ids: List[int]) -> List[Dict[str, Any]]:
    """Bulk hydrator reusing the efficient 6-query pattern from user.py."""
    if not user_ids:
        return []

    users_by_id = {
        u.id: u for u in User.objects.filter(id__in=user_ids).select_related("country", "state")
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

    # The email of the supervisor assigned to each student. A student's profile
    # points at their supervisor's profile, whose id is the supervisor's user id;
    # the supervisor is usually not on this page, so they are fetched separately.
    supervisor_ids = {
        sp.supervisor_id for sp in student_profiles.values() if sp.supervisor_id
    }
    supervisor_emails: Dict[int, str] = {
        u.id: u.email
        for u in User.objects.filter(id__in=supervisor_ids).only("id", "email")
    }

    # Active role assignments
    now = timezone.now()
    role_map: Dict[int, str] = {}
    for rah in RoleAssignmentHistory.objects.filter(user_id__in=user_ids).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related("role"):
        role_map[rah.user_id] = rah.role.role_name

    # Group memberships and matched mentor/mentee resolution
    group_map: Dict[int, Dict[str, Any]] = {}
    user_groups_map: Dict[int, List[Dict[str, Any]]] = {}
    user_group_ids = set()
    for gm in GroupMembership.objects.filter(
        user_id__in=user_ids, left_at__isnull=True, group__deleted_at__isnull=True
    ).select_related("group"):
        g_entry = {
            "id": gm.group.id,
            "name": gm.group.group_name,
        }
        group_map[gm.user_id] = g_entry
        user_groups_map.setdefault(gm.user_id, []).append(g_entry)
        user_group_ids.add(gm.group.id)

    # "Group Number" is the name of the group(s) a user belongs to, not how
    # many: a student is in one ("BTF182"), a mentor can be in several
    # ("BTF1, BTF6"). Ordered so BTF2 comes before BTF10.
    group_numbers_map: Dict[int, str] = {}
    for uid, g_list in user_groups_map.items():
        names = sorted({g["name"] for g in g_list}, key=natural_key)
        group_numbers_map[uid] = ", ".join(names)

    # Resolve partners (mentors for students, mentees for mentors)
    partner_map: Dict[int, str] = {}
    if user_group_ids:
        all_group_members = (
            GroupMembership.objects.filter(
                group_id__in=user_group_ids, left_at__isnull=True
            )
            .select_related("user")
            .values("group_id", "user_id", "user__first_name", "user__last_name", "membership_role")
        )
        group_mentors: Dict[int, List[str]] = {}
        group_students: Dict[int, List[str]] = {}
        for gm in all_group_members:
            gid = gm["group_id"]
            name = f"{gm['user__first_name']} {gm['user__last_name']}".strip()
            role = gm["membership_role"]
            if role == "mentor":
                group_mentors.setdefault(gid, []).append(name)
            elif role == "student":
                group_students.setdefault(gid, []).append(name)

        for uid, g_list in user_groups_map.items():
            urole = role_map.get(uid)
            if urole == "student":
                mentors: List[str] = []
                for ginfo in g_list:
                    for m_name in group_mentors.get(ginfo["id"], []):
                        if m_name not in mentors:
                            mentors.append(m_name)
                partner_map[uid] = f"Mentor: {', '.join(mentors)}" if mentors else "Mentor: Pending"
            elif urole == "mentor":
                students: List[str] = []
                for ginfo in g_list:
                    for s_name in group_students.get(ginfo["id"], []):
                        if s_name not in students:
                            students.append(s_name)
                partner_map[uid] = f"Mentee: {', '.join(students)}" if students else "No mentees"

    # User interests
    interests_map: Dict[int, List[str]] = {}
    for ui in UserInterest.objects.filter(user_id__in=user_ids).select_related("interest"):
        interests_map.setdefault(ui.user_id, []).append(ui.interest.interest_desc)

    users_list = []
    this_year = current_cohort()
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
        elif mp and mp.institution:
            school_name = mp.institution

        group_info = group_map.get(uid)
        user_groups = user_groups_map.get(uid, [])
        distinct_group_ids = {g["id"] for g in user_groups}

        # The role-specific fields. A mentor's details and a student's guardian
        # and supervisor details are only theirs, so a user of another role
        # gets nothing here and the column shows a dash.
        mentor_capacity = mp.max_group_count if mp else None
        mentor_background = mp.background if mp else None
        mentor_year_of_study = mp.university_year if mp else None
        mentor_field_of_study = mp.field_of_study if mp else None
        supervisor_email = supervisor_emails.get(sp.supervisor_id) if sp and sp.supervisor_id else None
        guardian_email = sp.pg_email if sp else None
        guardian_permission = sp.has_join_permission if sp else None

        users_list.append({
            "id": user.id,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "email": user.email,
            "pronouns": user.pronouns or "",
            "role": role_map.get(uid, "admin" if uid in admin_user_ids else "student"),
            "country": _user_country_dict(user),
            "state": _user_state_dict(user),
            "groupId": group_info["id"] if group_info else None,
            "groupName": group_info["name"] if group_info else None,
            "groupCount": len(distinct_group_ids),
            "groupNumbers": group_numbers_map.get(uid, ""),
            "schoolName": school_name,
            "matchedPartner": partner_map.get(uid, "-"),
            "mentorBackground": mentor_background,
            "mentorBackgroundLabel": mentor_background_label(mentor_background),
            "mentorInstitution": mp.institution if mp else None,
            "mentorGroupCapacity": mentor_capacity,
            "mentorYearOfStudy": mentor_year_of_study,
            "mentorFieldOfStudy": mentor_field_of_study,
            "supervisorEmail": supervisor_email,
            "guardianEmail": guardian_email,
            "guardianPermission": guardian_permission,
            "yearLevel": int(sp.year_lvl) if sp and sp.year_lvl else None,
            "earlierChallengeYear": earlier_challenge_year(sp, this_year),
            "interests": interests_map.get(uid, []),
            "isAdmin": uid in admin_user_ids,
            "isActive": user.is_active,
            "hasLoggedIn": user.last_login is not None,
            "lastLogin": user.last_login.isoformat() if user.last_login else None,
            "accountStatus": "active" if user.is_active else "inactive",
            "phone": getattr(user, "phone", "") or "",
        })

    return users_list


# ============================================================================
# CSV EXPORT
# ============================================================================

def export_view_csv(
    view: AdminView,
    search: Optional[str] = None,
    sort_by: str = "createdAt",
    sort_order: str = "desc",
) -> HttpResponse:
    """
    Streams an unpaginated CSV of matching users adhering strictly to visible_columns.
    """
    criteria = {
        "target_roles": view.target_roles,
        "account_status": view.account_status,
        "engagement_status": view.engagement_status,
        "advanced_conditions": view.advanced_conditions,
    }

    qs, order_by = build_view_queryset(
        criteria=criteria,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    user_ids = list(qs.values_list("id", flat=True).distinct().order_by(*order_by))

    users_list = _hydrate_users_by_ids(user_ids)
    visible_cols = view.visible_columns or ["name", "email", "role", "status"]

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    headers = [COLUMN_HEADER_MAP.get(col, col.replace("_", " ").title()) for col in visible_cols]
    writer.writerow(headers)

    # Data rows
    for u in users_list:
        row = []
        for col in visible_cols:
            val = _extract_column_value(u, col)
            row.append(val)
        writer.writerow(row)

    safe_title = re.sub(r"[^a-zA-Z0-9_\-]+", "_", view.name.strip().lower()).strip("_") or "view"
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}_export.csv"'
    return response


def _sanitize_csv_text(val: Any) -> str:
    """Normalizes non-ASCII punctuation (em/en-dash, smart quotes) for clean spreadsheet rendering."""
    if val is None:
        return ""
    text = str(val)
    return (
        text.replace("\u2014", "-")  # em-dash —
        .replace("\u2013", "-")      # en-dash –
        .replace("\u2212", "-")      # minus sign −
    )


def _extract_column_value(user_dict: Dict[str, Any], column_key: str) -> str:
    """Formats cell value for CSV output based on column key."""
    key = column_key.lower().strip().replace(" ", "_")
    if key in ("name", "full_name"):
        return _sanitize_csv_text(user_dict.get("name", ""))
    elif key == "email":
        return _sanitize_csv_text(user_dict.get("email", ""))
    elif key == "role":
        return (user_dict.get("role") or "").capitalize()
    elif key in ("school", "institution", "school_name", "school_/_institution"):
        return _sanitize_csv_text(
            user_dict.get("schoolName") or user_dict.get("mentorInstitution") or ""
        )
    elif key in ("matched_mentor", "matched_partner", "matched_mentor/group", "matched_mentor/mentee"):
        val = user_dict.get("matchedPartner") or ""
        return _sanitize_csv_text(val) if val not in ("—", "-") else "-"
    elif key == "status":
        return "Active" if user_dict.get("isActive") else "Inactive"
    elif key == "state":
        st = user_dict.get("state")
        if isinstance(st, dict):
            return _sanitize_csv_text(st.get("stateName") or st.get("name") or "-")
        return _sanitize_csv_text(st) if st else "-"
    elif key == "country":
        ct = user_dict.get("country")
        if isinstance(ct, dict):
            return _sanitize_csv_text(ct.get("countryName") or ct.get("name") or "Unassigned")
        return _sanitize_csv_text(ct) if ct else "Unassigned"
    elif key in ("interests", "interest"):
        interests = user_dict.get("interests") or []
        return _sanitize_csv_text(", ".join(interests)) if interests else ""
    elif key in ("last_login", "lastlogin"):
        last_login = user_dict.get("lastLogin")
        if not last_login:
            return "Never"
        return str(last_login).split("T")[0]
    elif key in ("year_level", "yearlevel", "year_lvl"):
        yl = user_dict.get("yearLevel")
        return str(yl) if yl is not None else ""
    elif key == "group":
        return _sanitize_csv_text(user_dict.get("groupName") or "")
    elif key in ("group_count", "groupcount", "number_of_groups"):
        gc = user_dict.get("groupCount")
        return str(gc if gc is not None else 0)
    elif key in ("group_number", "groupnumber"):
        return _sanitize_csv_text(user_dict.get("groupNumbers") or "")
    elif key == "phone":
        return _sanitize_csv_text(user_dict.get("phone", ""))
    elif key == "pronouns":
        return _sanitize_csv_text(user_dict.get("pronouns") or "") or "-"
    elif key in ("mentor_group_capacity", "group_capacity", "mentor_capacity", "max_group_count"):
        capacity = user_dict.get("mentorGroupCapacity")
        return str(capacity) if capacity is not None else "-"
    elif key == "mentor_background":
        return _sanitize_csv_text(user_dict.get("mentorBackgroundLabel") or "") or "-"
    elif key == "mentor_year_of_study":
        return _sanitize_csv_text(user_dict.get("mentorYearOfStudy") or "") or "-"
    elif key == "mentor_field_of_study":
        return _sanitize_csv_text(user_dict.get("mentorFieldOfStudy") or "") or "-"
    elif key == "supervisor_email":
        return _sanitize_csv_text(user_dict.get("supervisorEmail") or "") or "-"
    elif key == "guardian_email":
        return _sanitize_csv_text(user_dict.get("guardianEmail") or "") or "-"
    elif key == "guardian_permission":
        permission = user_dict.get("guardianPermission")
        if permission is None:
            return "-"
        return "Granted" if permission else "Not granted"

    return _sanitize_csv_text(user_dict.get(column_key, ""))


# ============================================================================
# SERIALIZERS
# ============================================================================

def serialize_admin_view(view: AdminView) -> Dict[str, Any]:
    """Serializes an AdminView model to JSON representation."""
    return {
        "id": view.id,
        "name": view.name,
        "description": view.description,
        "isDefault": view.is_default,
        "targetRoles": view.target_roles or [],
        "accountStatus": view.account_status,
        "engagementStatus": view.engagement_status,
        "advancedConditions": view.advanced_conditions or [],
        "visibleColumns": view.visible_columns or [],
        "lastRunAt": view.last_run_at.isoformat() if view.last_run_at else None,
        "createdAt": view.created_at.isoformat() if view.created_at else None,
        "updatedAt": view.updated_at.isoformat() if view.updated_at else None,
    }
