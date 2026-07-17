from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from django.db.models import Q, Count, F, Max, Value, CharField, Exists, OuterRef
from django.db.models.functions import Concat
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.groups.models import Groups, GroupMembership
from apps.users.models import User, MentorProfile, StudentProfile
from apps.users.models import UserInterest, AreasOfInterest
from apps.matching_runtime.models import MatchRun
from apps.common.tz import utc_offset_hours
from apps.admin.algorithms.mentor import match_mentors, score_mentor_for_group
from apps.admin.services.mentor import get_mentor_list


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


def _build_mentor_sources() -> List[Dict[str, Any]]:
    """All active mentors as algorithm 'mentor sources', with their current load."""
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


def recommend_mentors_for_group(group_id: int) -> Dict[str, Any]:
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
    for mentor in _build_mentor_sources():
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


def match_mentor(admin_user_id: str, mode: str = 'balanced') -> List[Dict[str, Any]]:
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
    
    mentor_sources = _build_mentor_sources()

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
            institution=F('user__mentorprofile__institution'),
            mentor_country_name=F('user__country__country_name'),
        )
    )

    if not rows:
        return []

    group_ids = [r['group_id'] for r in rows]

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
            'name': f"{row['first_name']} {row['last_name']}".strip(),
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
                'countryName': r['mentor_country_name'],
                'institution': r['institution'],
            },
        })

    return result


def replace_mentor(input_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Replace a mentor in a group with a new one.

    Args:
        input_data: Dictionary with membershipId, groupId, and newMentorUserId

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

    return {'replaced': 1}


def bulk_replace_inactive_mentors() -> Dict[str, int]:
    """
    Replace all inactive mentors with removal from groups.

    Returns:
        Dictionary with 'removedCount' of inactive mentor assignments
    """
    # Find inactive mentors in groups
    inactive_rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            user__is_active=False,
            user__mentorprofile__isnull=False
        )
        .values('id')
    )
    
    if not inactive_rows:
        return {'removedCount': 0}

    # Mark as left
    count = GroupMembership.objects.filter(
        id__in=[r['id'] for r in inactive_rows],
    ).update(left_at=timezone.now())

    return {'removedCount': count}


def confirm_mentor_assignments(input_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Confirm and finalize mentor assignments to groups.

    Args:
        input_data: Dictionary with 'assignments' list containing group-mentor mappings

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

    # Remove existing mentor assignments
    existing_mentor_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .values('id')
    )
    
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

    return {'confirmedCount': len(assignments)}


def unassign_mentors(group_ids: List[int]) -> Dict[str, int]:
    """
    Remove mentor assignments from groups.

    Args:
        group_ids: List of group IDs to unassign mentors from

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
        .values('id')
    )

    if not mentor_rows:
        return {'unassignedCount': 0}

    count = GroupMembership.objects.filter(
        id__in=[r['id'] for r in mentor_rows]
    ).update(left_at=timezone.now())

    return {'unassignedCount': count}
