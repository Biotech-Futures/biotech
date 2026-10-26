import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from django.db.models import Q, Count, F, Max, Value, CharField, Exists, OuterRef
from django.db.models.functions import Concat
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.chat.models import Messages
from apps.groups.models import Groups, GroupMembership
from apps.users.models import User, MentorProfile, StudentProfile
from apps.users.models import UserInterest, AreasOfInterest
from apps.services.system_email import send_system_email
from apps.matching_runtime.models import MatchRun
from apps.common.tz import utc_offset_hours
from apps.admin.algorithms.mentor import match_mentors, score_mentor_for_group
from apps.admin.services.mentor import get_mentor_list


logger = logging.getLogger(__name__)


def unmatched_groups_qs():
    """Live groups that need a mentor: no mentor member, and at least one student to mentor.

    Empty groups are excluded — a mentor on a 0-student group is meaningless, and the
    algorithm scores on student interests, so they would consume capacity for no benefit.
    """
    mentor_subquery = GroupMembership.objects.filter(
        group_id=OuterRef('id'),
        left_at__isnull=True,
        user__mentorprofile__isnull=False,
    )
    student_subquery = GroupMembership.objects.filter(
        group_id=OuterRef('id'),
        left_at__isnull=True,
        user__studentprofile__isnull=False,
    )

    return Groups.objects.filter(
        ~Exists(mentor_subquery),
        Exists(student_subquery),
        deleted_at__isnull=True,
    )


def _group_interests_by_key(rows: List[Dict], key_field: str, interest_field: str) -> Dict[Any, List[str]]:
    """Group interests by a key field"""
    interest_map = {}
    for row in rows:
        key = row[key_field]
        if key not in interest_map:
            interest_map[key] = []
        interest_map[key].append(row[interest_field])
    return interest_map


def _modal_country(countries: List[Optional[str]]) -> Optional[str]:
    """Most common non-empty country in a list; None when none are known."""
    counts: Dict[str, int] = {}
    for country in countries:
        if country:
            counts[country] = counts.get(country, 0) + 1
    if not counts:
        return None
    return max(sorted(counts.keys()), key=lambda country: counts[country])


def _median(values: List[float]) -> float:
    """Median of a list of numbers; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


#: What the Mentors page starts from, for a caller that names no threshold.
#: Mirrors DEFAULT_IDLE_DAYS in frontend/src/utils/mentorFormat.ts.
DEFAULT_IDLE_DAYS = 30


def _idle_mentor_ids(mentor_ids: List[int], idle_days: int) -> set:
    """Of ``mentor_ids``, those who should not be recommended.

    Idle is "has not spoken lately": no message within ``idle_days``. Silence
    only counts against a mentor who had somewhere to speak, so two groups are
    never idle however quiet they are:

    - one with no group at all, who has nowhere to post. Calling them idle
      would be a deadlock - they are excluded from matching for never having
      messaged, and can never message without a group to message in;
    - one who joined within ``idle_days``, who has not had the time yet.
    """
    if not mentor_ids:
        return set()

    cutoff = timezone.now() - timedelta(days=idle_days)
    spoke_recently = set(
        Messages.objects
        .filter(sender_user_id__in=mentor_ids, sent_at__gte=cutoff)
        .values_list('sender_user_id', flat=True)
    )
    joined_recently = set(
        User.objects
        .filter(id__in=mentor_ids, date_joined__gte=cutoff)
        .values_list('id', flat=True)
    )
    in_a_group = set(
        GroupMembership.objects
        .filter(user_id__in=mentor_ids, left_at__isnull=True)
        .values_list('user_id', flat=True)
    )
    no_group = set(mentor_ids) - in_a_group
    return set(mentor_ids) - spoke_recently - joined_recently - no_group


MAX_IDLE_DAYS = 365


def _requested_idle_days(input_data: Dict[str, Any]) -> int:
    """The admin's own "idle after" setting, as sent with the request.

    It has to travel with the mutation rather than be assumed here: an admin
    working to a 60-day threshold is shown mentors who are quiet at 30, and
    enforcing 30 server-side would reject the very replacements the screen just
    offered. Clamped so a stray or hostile value cannot switch the check off.
    """
    raw = input_data.get('idleDays', input_data.get('idle_days'))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_IDLE_DAYS
    return max(1, min(MAX_IDLE_DAYS, value))


def _assert_mentors_eligible(
    mentor_ids: List[int],
    idle_days: int,
    *,
    field: str,
    exempt_ids: Optional[Set[int]] = None,
    allow_idle: bool = False,
) -> None:
    """Refuse to assign a mentor the screens would not have offered.

    The admin screens and ``recommend_mentors_for_group`` both filter these
    out, but filtering is presentation: an older frontend, a scripted request
    or a replayed one reaches the mutation directly. Both mutation paths call
    this so the rule is enforced once, where it cannot be skipped.

    Two reasons to refuse, and they are different facts. A deactivated account
    is never assignable - that is not the admin's call to make here, it is made
    on the Users page. Idle is measured against ``idle_days``, so an admin who
    genuinely wants a quiet mentor can widen their own threshold rather than
    needing a back door.

    ``exempt_ids`` are mentors already sitting on the group they are being
    assigned to. Re-picking them changes nothing, so there is nothing to
    protect against, and refusing would block a harmless no-op.

    ``field`` is the request field to report against, named by the caller. It
    cannot be inferred from the number of mentors: a batch of one is still the
    batch path, and reporting it under the single-replace field would have the
    bulk dialog looking for an error where there is none.

    ``allow_idle`` is for the flows where an admin names the mentor rather than
    taking a suggestion - editing one mentor's own group list from their
    profile. Being quiet is a reason not to *suggest* someone, not a reason to
    stop an admin assigning them on purpose. It never waives the account check:
    a deactivated account stays unassignable by every path.
    """
    candidates = [m for m in mentor_ids if m not in (exempt_ids or set())]
    if not candidates:
        return

    deactivated = set(
        User.objects
        .filter(id__in=candidates, is_active=False)
        .values_list('id', flat=True)
    )
    # Only ask about the rest: a deactivated account is reported for that, which
    # is the more specific reason.
    idle = set() if allow_idle else _idle_mentor_ids(
        [m for m in candidates if m not in deactivated], idle_days
    )
    if not deactivated and not idle:
        return

    names = dict(
        User.objects
        .filter(id__in=deactivated | idle)
        .values_list('id', 'email')
    )
    raise ValidationError({
        field: {
            'message': (
                'One or more mentors cannot be assigned: a deactivated account '
                'is never assignable, and an idle one is not offered at the '
                'requested threshold.'
            ),
            'idleDays': idle_days,
            'ineligible': [
                {
                    'mentorUserId': mentor_id,
                    'email': names.get(mentor_id),
                    'reason': 'inactive' if mentor_id in deactivated else 'idle',
                }
                for mentor_id in sorted(deactivated | idle)
            ],
        },
    })


def _build_mentor_sources(idle_days: int = DEFAULT_IDLE_DAYS) -> List[Dict[str, Any]]:
    """Active, non-idle mentors as algorithm 'mentor sources', with their load."""
    accepted_count_rows = (
        GroupMembership.objects
        .filter(left_at__isnull=True, user__mentorprofile__isnull=False)
        .values('user_id')
        .annotate(count=Count('id'))
    )
    accepted_count_by_mentor = {row['user_id']: row['count'] for row in accepted_count_rows}

    mentor_rows = (
        MentorProfile.objects
        .filter(user__is_active=True)
        .select_related('user', 'user__country')
        .values(
            'institution',
            mentor_id=F('user_id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            max_grp_cnt=F('max_group_count'),
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )
    mentor_ids = [m['mentor_id'] for m in mentor_rows]

    # Quiet mentors are not offered fresh groups: assigning to someone who has
    # stopped answering is how a group ends up without support.
    idle_ids = _idle_mentor_ids(mentor_ids, idle_days)
    if idle_ids:
        mentor_rows = [m for m in mentor_rows if m['mentor_id'] not in idle_ids]
        mentor_ids = [m['mentor_id'] for m in mentor_rows]

    mentor_interest_rows = (
        UserInterest.objects
        .filter(user_id__in=mentor_ids)
        .select_related('interest')
        .values(key=F('user_id'), interest_desc=F('interest__interest_desc'))
    ) if mentor_ids else []
    interests_by_mentor = _group_interests_by_key(mentor_interest_rows, 'key', 'interest_desc')

    return [
        {
            'mentorId': m['mentor_id'],
            'firstName': m['first_name'],
            'lastName': m['last_name'],
            'institution': m['institution'],
            'countryName': m['country_name'],
            'utcOffsetHours': utc_offset_hours(m['user_tz']),
            'interests': interests_by_mentor.get(m['mentor_id'], []),
            'maxGroupCount': m['max_grp_cnt'],
            'currentAcceptedCount': accepted_count_by_mentor.get(m['mentor_id'], 0),
        }
        for m in mentor_rows
    ]


def _build_group_source(group) -> Dict[str, Any]:
    """A single group's algorithm 'group source' from its active student members."""
    geo_rows = list(
        GroupMembership.objects
        .filter(group_id=group.id, left_at__isnull=True, user__studentprofile__isnull=False)
        .select_related('user', 'user__country')
        .values('user_id', country_name=F('user__country__country_name'),
                user_tz=F('user__timezone'))
    )
    student_ids = [r['user_id'] for r in geo_rows]
    interest_rows = (
        UserInterest.objects
        .filter(user_id__in=student_ids)
        .values(interest_desc=F('interest__interest_desc'))
    ) if student_ids else []

    return {
        'groupId': group.id,
        'groupName': group.group_name,
        'countryName': _modal_country([r['country_name'] for r in geo_rows]),
        'utcOffsetHours': _median([utc_offset_hours(r['user_tz']) for r in geo_rows]),
        'studentInterests': [r['interest_desc'] for r in interest_rows if r['interest_desc']],
        'studentCount': len(student_ids),
    }


def recommend_mentors_for_group(group_id: int, idle_days: int = DEFAULT_IDLE_DAYS) -> Dict[str, Any]:
    """Rank replacement mentors for one group (even one that already has a mentor).

    Reuses the same scoring as auto-matching, but for a single group that the auto
    matcher would skip. The group's current active mentor(s) are excluded; the rest
    are returned best-first with score, breakdown, reason, and remaining capacity.
    """
    try:
        group = Groups.objects.get(id=group_id, deleted_at__isnull=True)
    except Groups.DoesNotExist:
        return {"msg": "Group not found", "data": None}

    current_mentor_ids = set(
        GroupMembership.objects
        .filter(group_id=group_id, left_at__isnull=True, user__mentorprofile__isnull=False)
        .values_list('user_id', flat=True)
    )

    group_source = _build_group_source(group)
    suggestions = []
    for mentor in _build_mentor_sources(idle_days):
        if mentor['mentorId'] in current_mentor_ids:
            continue
        score, breakdown, reason = score_mentor_for_group(mentor, group_source)
        remaining = mentor['maxGroupCount'] - mentor['currentAcceptedCount']
        suggestions.append({
            'mentorUserId': mentor['mentorId'],
            'name': f"{mentor['firstName']} {mentor['lastName']}".strip(),
            'institution': mentor['institution'],
            'remainingCapacity': remaining,
            'atCapacity': remaining <= 0,
            'score': score,
            'reason': reason,
            'scoreBreakdown': breakdown,
        })

    # Best first; push over-capacity mentors down; stable tiebreak on name.
    suggestions.sort(key=lambda s: (-s['score'], s['atCapacity'], s['name']))

    return {
        "msg": "Mentor suggestions computed",
        "data": {
            "groupId": group.id,
            "groupName": group.group_name,
            "suggestions": suggestions,
        },
    }


def match_mentor(admin_user_id: str, mode: str = 'balanced',
                 idle_days: int = DEFAULT_IDLE_DAYS) -> List[Dict[str, Any]]:
    """
    Run mentor matching algorithm for groups without mentors.
    
    Args:
        admin_user_id: Admin user ID initiating the match
        mode: Matching mode ('balanced', 'strict', etc.)
        
    Returns:
        List of mentor match recommendations
    """
    # Find groups without mentors
    groups_without_mentor = (
        unmatched_groups_qs()
        .values(
            'group_name',
            group_id=F('id'),
        )
    )

    if not groups_without_mentor:
        return []

    group_ids = [g['group_id'] for g in groups_without_mentor]

    # Collect student interests per group
    member_interest_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user')
        .values(
            'group_id',
            interest_desc=F('user__userinterest__interest__interest_desc'),
        )
    )

    interests_by_group = _group_interests_by_key(
        [r for r in member_interest_rows if r['interest_desc']],
        'group_id',
        'interest_desc'
    )

    # Count members per group
    member_count_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .values('group_id')
        .annotate(count=Count('id'))
    )

    member_count_by_group = {row['group_id']: row['count'] for row in member_count_rows}

    # Group geography: modal country + median timezone offset of active members.
    member_geo_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user', 'user__country')
        .values(
            'group_id',
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )

    countries_by_group: Dict[Any, List[Optional[str]]] = {}
    offsets_by_group: Dict[Any, List[float]] = {}
    for row in member_geo_rows:
        gid = row['group_id']
        countries_by_group.setdefault(gid, []).append(row['country_name'])
        offsets_by_group.setdefault(gid, []).append(utc_offset_hours(row['user_tz']))

    # Build group sources
    group_sources = [
        {
            'groupId': g['group_id'],
            'groupName': g['group_name'],
            'countryName': _modal_country(countries_by_group.get(g['group_id'], [])),
            'utcOffsetHours': _median(offsets_by_group.get(g['group_id'], [])),
            'studentInterests': interests_by_group.get(g['group_id'], []),
            'studentCount': member_count_by_group.get(g['group_id'], 0),
        }
        for g in groups_without_mentor
    ]
    
    mentor_sources = _build_mentor_sources(idle_days)

    # Run matching algorithm using the same data shape as admin/apps/server/src/algorithm/mentor.ts.
    recommendations = match_mentors(group_sources, mentor_sources, mode)
    
    # Save match run
    MatchRun.objects.create(
        initiated_by_user_id=int(admin_user_id),
        run_type='mentor-match',
        rules_snapshot=group_sources,
    )
    
    return recommendations


def get_mentors(requesting_user=None) -> List[Dict[str, Any]]:
    """
    Get mentors using the same response shape as the admin mentor module.

    Returns:
        List of mentor dictionaries
    """
    return get_mentor_list(requesting_user=requesting_user)


def get_unmatched_groups(requesting_user=None) -> List[Dict[str, Any]]:
    """
    Get all groups without mentors.

    Returns:
        List of unmatched group dictionaries
    """
    unmatched_groups_base = (
        unmatched_groups_qs()
        .values(
            'group_name',
            group_id=F('id'),
        )
    )

    if not unmatched_groups_base:
        return []
    
    group_ids = [g['group_id'] for g in unmatched_groups_base]
    
    # Member interests
    member_interest_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user')
        .values(
            'group_id',
            'user_id',
            interest_desc=F('user__userinterest__interest__interest_desc'),
        )
    )
    
    interests_by_group = {}
    interests_by_user = {}
    for row in member_interest_rows:
        if row['interest_desc']:
            if row['group_id'] not in interests_by_group:
                interests_by_group[row['group_id']] = []
            interests_by_group[row['group_id']].append(row['interest_desc'])
            if row['user_id'] not in interests_by_user:
                interests_by_user[row['user_id']] = []
            interests_by_user[row['user_id']].append(row['interest_desc'])
    
    # Student names
    student_name_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user', 'user__country')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            country_name=F('user__country__country_name'),
            last_login=F('user__last_login'),
        )
    )

    students_by_group = {}
    countries_by_group: Dict[Any, List[Optional[str]]] = {}
    for row in student_name_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'user_id': row['user_id'],
            'name': f"{row['first_name']} {row['last_name']}".strip(),
            # Boolean, never the timestamp: admins need "have they started?".
            'hasLoggedIn': row['last_login'] is not None,
        })
        countries_by_group.setdefault(group_id, []).append(row['country_name'])

    result = []
    for g in unmatched_groups_base:
        group_students = students_by_group.get(g['group_id'], [])
        result.append({
            'groupId': g['group_id'],
            'groupName': g['group_name'],
            'countryName': _modal_country(countries_by_group.get(g['group_id'], [])),
            'studentInterests': interests_by_group.get(g['group_id'], []),
            'studentCount': len(group_students),
            'students': [
                {
                    'name': s['name'],
                    'hasLoggedIn': s['hasLoggedIn'],
                    'interests': interests_by_user.get(s['user_id'], []),
                }
                for s in group_students
            ],
        })

    return result


def get_matched_groups(requesting_user=None) -> List[Dict[str, Any]]:
    """
    Get all groups with assigned mentors.

    Returns:
        List of matched group dictionaries with mentor and student info
    """
    membership_qs = GroupMembership.objects.filter(
        left_at__isnull=True,
        group__deleted_at__isnull=True,
        user__mentorprofile__isnull=False
    )

    rows = (
        membership_qs
        .select_related('group', 'user', 'user__country')
        .values(
            'group_id',
            membership_id=F('id'),
            group_name=F('group__group_name'),
            mentor_id=F('user_id'),
            mentor_first_name=F('user__first_name'),
            mentor_last_name=F('user__last_name'),
            is_active=F('user__is_active'),
            mentor_date_joined=F('user__date_joined'),
            institution=F('user__mentorprofile__institution'),
            mentor_country_name=F('user__country__country_name'),
        )
    )

    if not rows:
        return []

    group_ids = [r['group_id'] for r in rows]

    # Last message per mentor, so the caller can tell a mentor who has gone
    # quiet (idle) from one whose account was deactivated. Same aggregation the
    # Mentors page uses - see apps.admin.services.mentor.
    last_message_by_mentor = {
        row['sender_user_id']: row['last_message_at']
        for row in (
            Messages.objects
            .filter(deleted_at__isnull=True, sender_user_id__in=[r['mentor_id'] for r in rows])
            .values('sender_user_id')
            .annotate(last_message_at=Max('sent_at'))
        )
    }

    # Student names per group
    student_name_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user', 'user__country')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            country_name=F('user__country__country_name'),
            last_login=F('user__last_login'),
        )
    )

    # Student interests per group
    member_interest_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user')
        .values(
            'group_id',
            'user_id',
            interest_desc=F('user__userinterest__interest__interest_desc'),
        )
    )
    
    interests_by_user = {}
    for row in member_interest_rows:
        if row['interest_desc']:
            if row['user_id'] not in interests_by_user:
                interests_by_user[row['user_id']] = []
            interests_by_user[row['user_id']].append(row['interest_desc'])
    
    students_by_group = {}
    countries_by_group: Dict[Any, List[Optional[str]]] = {}
    for row in student_name_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'id': row['user_id'],
            'name': f"{row['first_name']} {row['last_name']}".strip(),
            'hasLoggedIn': row['last_login'] is not None,
            'interests': interests_by_user.get(row['user_id'], []),
        })
        countries_by_group.setdefault(group_id, []).append(row['country_name'])

    result = []
    for r in rows:
        students = students_by_group.get(r['group_id'], [])
        result.append({
            'membershipId': r['membership_id'],
            'groupId': r['group_id'],
            'groupName': r['group_name'],
            'countryName': _modal_country(countries_by_group.get(r['group_id'], [])),
            'studentCount': len(students),
            'students': students,
            'mentor': {
                'mentorId': r['mentor_id'],
                'name': f"{r['mentor_first_name']} {r['mentor_last_name']}".strip(),
                'isActive': r['is_active'],
                'dateJoined': (
                    r['mentor_date_joined'].isoformat()
                    if r['mentor_date_joined'] else None
                ),
                'lastMessageAt': (
                    last_message_by_mentor[r['mentor_id']].isoformat()
                    if last_message_by_mentor.get(r['mentor_id'])
                    else None
                ),
                'countryName': r['mentor_country_name'],
                'institution': r['institution'],
            },
        })

    return result


def _notify_mentor_change(email_key, user_id, group_name, initiated_by=None):
    """Tell one mentor that a group moved to or away from them.

    Best effort on purpose: a bounced notification must not undo a membership
    change the admin already confirmed, so a failure is swallowed here and
    surfaces through the system-email log like every other send.
    """
    user = User.objects.filter(id=user_id).only("email", "first_name").first()
    if not user or not user.email:
        return
    try:
        send_system_email(
            email_key,
            [user.email],
            {
                "MENTOR_FIRST_NAME": user.first_name or "",
                "GROUP_NAME": group_name or "",
            },
            sent_by=initiated_by,
        )
    except Exception:
        logger.exception("mentor_change_email.failed key=%s user=%s", email_key, user_id)


def replace_mentor(input_data: Dict[str, Any], initiated_by=None) -> Dict[str, int]:
    """
    Replace a mentor in a group with a new one.

    Args:
        input_data: Dictionary with membershipId, groupId, and newMentorUserId.
            ``notifyDeparting`` / ``notifyIncoming`` control the two emails and
            default to True - the admin opts out, not in.

    Returns:
        Dictionary with 'replaced' count
    """
    new_mentor_id = input_data['newMentorUserId']
    group_id = input_data['groupId']

    profile = (
        MentorProfile.objects
        .filter(user_id=new_mentor_id)
        .values('max_group_count')
        .first()
    )
    if profile is None:
        raise ValidationError({'newMentorUserId': 'User is not a mentor.'})

    surviving_count = (
        GroupMembership.objects
        .filter(
            user_id=new_mentor_id,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .exclude(group_id=group_id)
        .count()
    )
    if surviving_count >= profile['max_group_count']:
        raise ValidationError({
            'newMentorUserId': (
                f'Mentor is at capacity '
                f'({surviving_count}/{profile["max_group_count"]}).'
            ),
        })

    # A mentor the screens would not have offered must not be assignable by a
    # request that skipped them. Re-picking the mentor already on the group is
    # a no-op, so it stays allowed however quiet they are.
    already_on_group = set(
        GroupMembership.objects
        .filter(
            group_id=group_id,
            user_id=new_mentor_id,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .values_list('user_id', flat=True)
    )
    _assert_mentors_eligible(
        [new_mentor_id],
        _requested_idle_days(input_data),
        field='newMentorUserId',
        exempt_ids=already_on_group,
    )

    # Who is leaving, read before the row is closed.
    departing_id = (
        GroupMembership.objects
        .filter(id=input_data['membershipId'], group_id=group_id, left_at__isnull=True)
        .values_list('user_id', flat=True)
        .first()
    )

    # Mark old mentor as left
    GroupMembership.objects.filter(
        id=input_data['membershipId'],
        group_id=group_id,
        left_at__isnull=True,
    ).update(left_at=timezone.now())

    # Add new mentor
    GroupMembership.objects.create(
        group_id=group_id,
        user_id=new_mentor_id,
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        joined_at=timezone.now(),
    )

    group_name = (
        Groups.objects.filter(id=group_id).values_list('group_name', flat=True).first()
    )
    # Re-picking the mentor already on the group is a no-op from their side, so
    # telling them they have been removed and re-added would be nonsense.
    unchanged = departing_id == new_mentor_id
    if departing_id and not unchanged and input_data.get('notifyDeparting', True):
        _notify_mentor_change('mentor_unassigned', departing_id, group_name, initiated_by)
    if not unchanged and input_data.get('notifyIncoming', True):
        _notify_mentor_change('mentor_assigned', new_mentor_id, group_name, initiated_by)

    return {'replaced': 1}


def confirm_mentor_assignments(input_data: Dict[str, Any], initiated_by=None) -> Dict[str, int]:
    """
    Confirm and finalize mentor assignments to groups.

    Args:
        input_data: Dictionary with 'assignments' list containing group-mentor
            mappings. ``notifyDeparting`` / ``notifyIncoming`` cover the whole
            batch and default to True.

    Returns:
        Dictionary with 'confirmedCount' of assignments
    """
    assignments = input_data.get('assignments', [])

    if not assignments:
        return {'confirmedCount': 0}

    # Deduplicate by group
    unique_by_group = {}
    for item in assignments:
        unique_by_group[item['groupId']] = item['mentorUserId']

    assignments = [
        {'group_id': gid, 'mentor_user_id': mid}
        for gid, mid in unique_by_group.items()
    ]

    group_ids = [a['group_id'] for a in assignments]

    # Capacity check: surviving live assignments (outside group_ids) + new
    # assignments must not exceed each mentor's max_group_count.
    mentor_ids = list({a['mentor_user_id'] for a in assignments})

    max_counts = {
        row['user_id']: row['max_group_count']
        for row in MentorProfile.objects
            .filter(user_id__in=mentor_ids)
            .values('user_id', 'max_group_count')
    }
    missing = [mid for mid in mentor_ids if mid not in max_counts]
    if missing:
        raise ValidationError({
            'assignments': f'Not a mentor: user IDs {missing}.',
        })

    surviving_counts = dict.fromkeys(mentor_ids, 0)
    for row in (
        GroupMembership.objects
        .filter(
            user_id__in=mentor_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .exclude(group_id__in=group_ids)
        .values('user_id')
        .annotate(count=Count('id'))
    ):
        surviving_counts[row['user_id']] = row['count']

    new_counts = {}
    for a in assignments:
        mid = a['mentor_user_id']
        new_counts[mid] = new_counts.get(mid, 0) + 1

    over_capacity = [
        {
            'mentorUserId': mid,
            'requested': surviving_counts[mid] + new_counts[mid],
            'maxGroupCount': max_counts[mid],
        }
        for mid in mentor_ids
        if surviving_counts[mid] + new_counts[mid] > max_counts[mid]
    ]
    if over_capacity:
        raise ValidationError({
            'assignments': {
                'message': 'One or more mentors would exceed max_group_count.',
                'overCapacity': over_capacity,
            },
        })

    # Same rule as the single replace, enforced on the batch path too.
    sitting = {
        (row['user_id'], row['group_id'])
        for row in GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .values('user_id', 'group_id')
    }
    # Exempt only a mentor whose every assignment in this batch is a no-op. One
    # who already sits on group A is still newly arriving at group B, and that
    # arrival is what the check is for.
    unchanged_mentors = {
        mentor_id
        for mentor_id in mentor_ids
        if all(
            (mentor_id, a['group_id']) in sitting
            for a in assignments
            if a['mentor_user_id'] == mentor_id
        )
    }
    # Set by the flow that edits one mentor's own group list, where the admin
    # picked the person deliberately. The matcher and the replacement dialogs
    # leave it off, so a suggestion-driven path cannot assign a quiet mentor.
    allow_idle = input_data.get('allowIdle', input_data.get('allow_idle')) is True
    _assert_mentors_eligible(
        mentor_ids,
        _requested_idle_days(input_data),
        field='assignments',
        exempt_ids=unchanged_mentors,
        allow_idle=allow_idle,
    )

    # Remove existing mentor assignments
    existing_mentor_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .values('id', 'user_id', 'group_id')
    )
    departing = [(r['user_id'], r['group_id']) for r in existing_mentor_rows]

    if existing_mentor_rows:
        GroupMembership.objects.filter(
            id__in=[r['id'] for r in existing_mentor_rows]
        ).update(left_at=timezone.now())
    
    # Create new assignments
    now = timezone.now()
    memberships = [
        GroupMembership(
            group_id=a['group_id'],
            user_id=a['mentor_user_id'],
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
            joined_at=now,
        )
        for a in assignments
    ]
    
    GroupMembership.objects.bulk_create(memberships)

    names = dict(
        Groups.objects.filter(id__in=group_ids).values_list('id', 'group_name')
    )
    # Groups whose mentor did not actually change: picking the sitting mentor
    # again is a no-op, so neither side hears about it.
    incoming_by_group = {a['group_id']: a['mentor_user_id'] for a in assignments}
    unchanged_groups = {
        group_id
        for user_id, group_id in departing
        if incoming_by_group.get(group_id) == user_id
    }

    if input_data.get('notifyDeparting', True):
        for user_id, group_id in departing:
            if group_id in unchanged_groups:
                continue
            _notify_mentor_change(
                'mentor_unassigned', user_id, names.get(group_id), initiated_by,
            )
    if input_data.get('notifyIncoming', True):
        for a in assignments:
            if a['group_id'] in unchanged_groups:
                continue
            _notify_mentor_change(
                'mentor_assigned', a['mentor_user_id'],
                names.get(a['group_id']), initiated_by,
            )

    return {'confirmedCount': len(assignments)}


def unassign_mentors(
    group_ids: List[int], notify_departing: bool = True, initiated_by=None,
) -> Dict[str, int]:
    """
    Remove mentor assignments from groups.

    Args:
        group_ids: List of group IDs to unassign mentors from
        notify_departing: Tell each removed mentor they are no longer on the
            group. Nobody is arriving, so there is no incoming side here.

    Returns:
        Dictionary with 'unassignedCount' of removed assignments
    """
    mentor_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .values('id', 'user_id', 'group_id')
    )

    if not mentor_rows:
        return {'unassignedCount': 0}

    count = GroupMembership.objects.filter(
        id__in=[r['id'] for r in mentor_rows]
    ).update(left_at=timezone.now())

    if notify_departing:
        names = dict(
            Groups.objects.filter(id__in=group_ids).values_list('id', 'group_name')
        )
        for row in mentor_rows:
            _notify_mentor_change(
                'mentor_unassigned', row['user_id'],
                names.get(row['group_id']), initiated_by,
            )

    return {'unassignedCount': count}
