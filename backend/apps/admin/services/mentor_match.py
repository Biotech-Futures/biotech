from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from django.db.models import Q, Count, F, Max, Value, CharField, Exists, OuterRef
from django.db.models.functions import Concat
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.users.models import User, MentorProfile, StudentProfile
from apps.users.models import UserInterest, AreasOfInterest
from apps.chat.models import Messages
from apps.matching_runtime.models import MatchRun
from apps.admin.algorithms.mentor import match_mentors
from apps.admin.services.mentor import get_mentor_list
from apps.admin.scope_utils import get_admin_track_ids


DEFAULT_INACTIVE_DAYS = 30


def _group_interests_by_key(rows: List[Dict], key_field: str, interest_field: str) -> Dict[Any, List[str]]:
    """Group interests by a key field"""
    interest_map = {}
    for row in rows:
        key = row[key_field]
        if key not in interest_map:
            interest_map[key] = []
        interest_map[key].append(row[interest_field])
    return interest_map


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
    mentor_subquery = GroupMembership.objects.filter(
        group_id=OuterRef('id'),
        left_at__isnull=True,
        user__mentorprofile__isnull=False
    )
    
    groups_without_mentor = (
        Groups.objects
        .filter(
            
            ~Exists(mentor_subquery), deleted_at__isnull=True
        )
        .select_related('track')
        .values(
            'group_name',
            group_id=F('id'),
            group_track_code=F('track__track_name'),
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
        .select_related('user__track')
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
    
    # Build group sources
    group_sources = [
        {
            'groupId': g['group_id'],
            'groupName': g['group_name'],
            'trackCode': g['group_track_code'],
            'studentInterests': interests_by_group.get(g['group_id'], []),
            'studentCount': member_count_by_group.get(g['group_id'], 0),
        }
        for g in groups_without_mentor
    ]
    
    # Get active mentors
    accepted_count_rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .values('user_id')
        .annotate(count=Count('id'))
    )
    
    accepted_count_by_mentor = {row['user_id']: row['count'] for row in accepted_count_rows}
    
    mentor_rows = (
        MentorProfile.objects
        .filter(user__is_active=True)
        .select_related('user', 'user__track')
        .values(
            'institution',
            mentor_id=F('user_id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            max_grp_cnt=F('max_group_count'),
            track_code=F('user__track__track_name'),
        )
    )
    
    mentor_ids = [m['mentor_id'] for m in mentor_rows]
    
    mentor_interest_rows = (
        UserInterest.objects
        .filter(user_id__in=mentor_ids)
        .select_related('interest')
        .values(
            key=F('user_id'),
            interest_desc=F('interest__interest_desc'),
        )
    ) if mentor_ids else []
    
    interests_by_mentor = _group_interests_by_key(mentor_interest_rows, 'key', 'interest_desc')
    
    # Build mentor sources
    mentor_sources = [
        {
            'mentorId': m['mentor_id'],
            'firstName': m['first_name'],
            'lastName': m['last_name'],
            'institution': m['institution'],
            'trackCode': m['track_code'],
            'interests': interests_by_mentor.get(m['mentor_id'], []),
            'maxGroupCount': m['max_grp_cnt'],
            'currentAcceptedCount': accepted_count_by_mentor.get(m['mentor_id'], 0),
        }
        for m in mentor_rows
    ]
    
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
    mentor_subquery = GroupMembership.objects.filter(
        group_id=OuterRef('id'),
        left_at__isnull=True,
        user__mentorprofile__isnull=False
    )

    groups_qs = Groups.objects.filter(~Exists(mentor_subquery), deleted_at__isnull=True)
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        groups_qs = groups_qs.filter(Q(track_id__in=track_ids) | Q(track__isnull=True))

    unmatched_groups_base = (
        groups_qs
        .select_related('track')
        .values(
            'group_name',
            group_id=F('id'),
            track_code=F('track__track_name'),
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
        .select_related('user')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
        )
    )
    
    students_by_group = {}
    for row in student_name_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'user_id': row['user_id'],
            'name': f"{row['first_name']} {row['last_name']}".strip(),
        })
    
    result = []
    for g in unmatched_groups_base:
        group_students = students_by_group.get(g['group_id'], [])
        result.append({
            'groupId': g['group_id'],
            'groupName': g['group_name'],
            'trackCode': g['track_code'],
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
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        membership_qs = membership_qs.filter(
            Q(group__track_id__in=track_ids) | Q(group__track__isnull=True)
        )

    rows = (
        membership_qs
        .select_related('group', 'group__track', 'user')
        .values(
            'group_id',
            membership_id=F('id'),
            group_name=F('group__group_name'),
            group_track_id=F('group__track_id'),
            mentor_id=F('user_id'),
            mentor_first_name=F('user__first_name'),
            mentor_last_name=F('user__last_name'),
            is_active=F('user__is_active'),
            institution=F('user__mentorprofile__institution'),
            mentor_track_id=F('user__track_id'),
        )
    )
    
    if not rows:
        return []
    
    group_ids = [r['group_id'] for r in rows]
    
    # Get all track IDs
    all_track_ids = set()
    for row in rows:
        all_track_ids.add(row['group_track_id'])
        if row['mentor_track_id']:
            all_track_ids.add(row['mentor_track_id'])
    
    track_rows = (
        Tracks.objects
        .filter(id__in=all_track_ids)
        .values('id', 'track_name')
    )
    
    track_name_by_id = {row['id']: row['track_name'] for row in track_rows}
    
    # Student names per group
    student_name_rows = (
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
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
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
    for row in student_name_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'name': f"{row['first_name']} {row['last_name']}".strip(),
            'interests': interests_by_user.get(row['user_id'], []),
        })
    
    result = []
    for r in rows:
        students = students_by_group.get(r['group_id'], [])
        result.append({
            'membershipId': r['membership_id'],
            'groupId': r['group_id'],
            'groupName': r['group_name'],
            'trackCode': track_name_by_id.get(r['group_track_id'], ''),
            'studentCount': len(students),
            'students': students,
            'mentor': {
                'mentorId': r['mentor_id'],
                'name': f"{r['mentor_first_name']} {r['mentor_last_name']}".strip(),
                'isActive': r['is_active'],
                'trackCode': track_name_by_id.get(r['mentor_track_id'], '') if r['mentor_track_id'] else '',
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
    # Mark old mentor as left
    GroupMembership.objects.filter(
        id=input_data['membershipId'],
        group_id=input_data['groupId'],
        left_at__isnull=True,
    ).update(left_at=timezone.now())

    # Add new mentor
    GroupMembership.objects.create(
        group_id=input_data['groupId'],
        user_id=input_data['newMentorUserId'],
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        joined_at=timezone.now(),
    )
    
    return {'replaced': 1}


def _coerce_inactive_days(inactive_days: Any) -> int:
    """
    Coerce a user-supplied threshold into a positive integer. Falls back to
    DEFAULT_INACTIVE_DAYS when the value is missing or unparseable.
    """
    if inactive_days is None:
        return DEFAULT_INACTIVE_DAYS
    try:
        value = int(inactive_days)
    except (TypeError, ValueError):
        return DEFAULT_INACTIVE_DAYS
    return value if value >= 1 else DEFAULT_INACTIVE_DAYS


def get_inactive_mentor_membership_ids(
    inactive_days: int = DEFAULT_INACTIVE_DAYS,
) -> List[int]:
    """
    Identify active mentor group memberships whose mentor is "effectively inactive":

      - the user account is deactivated (`is_active=False`), OR
      - the mentor has not sent a non-deleted chat message within
        `inactive_days` days (mentors who never sent a message count as
        inactive by this engagement signal).

    Returns the membership ids that should be replaced.
    """
    cutoff = timezone.now() - timedelta(days=inactive_days)

    recent_message_subquery = Messages.objects.filter(
        sender_user_id=OuterRef('user_id'),
        deleted_at__isnull=True,
        sent_at__gte=cutoff,
    )

    rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .annotate(has_recent_message=Exists(recent_message_subquery))
        .filter(
            Q(user__is_active=False) | Q(has_recent_message=False),
        )
        .values_list('id', flat=True)
    )
    return list(rows)


def bulk_replace_inactive_mentors(
    inactive_days: Any = DEFAULT_INACTIVE_DAYS,
) -> Dict[str, int]:
    """
    Clear group assignments for mentors that have gone quiet or been
    deactivated. A mentor is considered inactive when either:

      - `user.is_active = False`, or
      - they have not sent a non-deleted message within `inactive_days` days
        (mentors who have never messaged count as inactive).

    Args:
        inactive_days: Engagement window threshold in days. Values below 1 or
            that fail to parse are coerced to DEFAULT_INACTIVE_DAYS.

    Returns:
        Dictionary with 'removedCount' of cleared mentor memberships and the
        'inactiveDays' threshold that was applied.
    """
    window_days = _coerce_inactive_days(inactive_days)

    membership_ids = get_inactive_mentor_membership_ids(window_days)
    if not membership_ids:
        return {'removedCount': 0, 'inactiveDays': window_days}

    count = GroupMembership.objects.filter(
        id__in=membership_ids,
    ).update(left_at=timezone.now())

    return {'removedCount': count, 'inactiveDays': window_days}


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

    # Spec §2.6: enforce mentor capacity. A confirm cannot push a mentor's
    # active group assignments beyond their configured maxGroupCount.
    _assert_assignments_within_capacity(assignments, group_ids)

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


def _assert_assignments_within_capacity(
    assignments: List[Dict[str, Any]],
    group_ids_being_reassigned: List[int],
) -> None:
    """
    Reject the confirm operation if any mentor would end up with more active
    group memberships than their maxGroupCount (Spec §2.6).

    Mentor memberships in `group_ids_being_reassigned` are not counted toward
    the existing load, because the confirm replaces those memberships.
    """
    mentor_ids = sorted({a['mentor_user_id'] for a in assignments})
    if not mentor_ids:
        return

    caps_by_mentor = {
        row['user_id']: row['max_group_count']
        for row in MentorProfile.objects.filter(user_id__in=mentor_ids).values(
            'user_id', 'max_group_count',
        )
    }

    # Active mentor memberships outside the groups being reassigned in this call.
    other_assignment_rows = (
        GroupMembership.objects
        .filter(
            user_id__in=mentor_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .exclude(group_id__in=group_ids_being_reassigned)
        .values('user_id')
        .annotate(count=Count('id'))
    )
    other_count_by_mentor = {row['user_id']: row['count'] for row in other_assignment_rows}

    new_count_by_mentor: Dict[int, int] = {}
    for a in assignments:
        new_count_by_mentor[a['mentor_user_id']] = (
            new_count_by_mentor.get(a['mentor_user_id'], 0) + 1
        )

    over_capacity: List[Dict[str, Any]] = []
    missing_profiles: List[int] = []
    for mentor_id, new_count in new_count_by_mentor.items():
        cap = caps_by_mentor.get(mentor_id)
        if cap is None:
            missing_profiles.append(mentor_id)
            continue
        existing = other_count_by_mentor.get(mentor_id, 0)
        projected = existing + new_count
        if projected > cap:
            over_capacity.append({
                "mentorUserId": mentor_id,
                "maxGroupCount": cap,
                "currentAssignedCount": existing,
                "requested": new_count,
                "wouldAssign": projected,
            })

    errors: Dict[str, Any] = {}
    if missing_profiles:
        errors["missingMentorProfiles"] = sorted(missing_profiles)
    if over_capacity:
        errors["overCapacity"] = over_capacity
    if errors:
        raise ValidationError({"assignments": errors})


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
