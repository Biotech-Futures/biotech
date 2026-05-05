from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from django.db.models import Q, Count, F, Max, Value, CharField, Exists, OuterRef
from django.db.models.functions import Concat
from django.utils import timezone
from django.db import transaction

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.users.models import User, MentorProfile, StudentProfile
from apps.users.models import UserInterest, AreasOfInterest
from apps.matching_runtime.models import MatchRun
from apps.admin.algorithms.mentor import match_mentors
from apps.admin.services.mentor import get_mentor_list


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


def get_mentors() -> List[Dict[str, Any]]:
    """
    Get mentors using the same response shape as the admin mentor module.
    
    Returns:
        List of mentor dictionaries
    """
    return get_mentor_list()


def get_unmatched_groups() -> List[Dict[str, Any]]:
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
    
    unmatched_groups_base = (
        Groups.objects
        .filter(
            
            ~Exists(mentor_subquery), deleted_at__isnull=True
        )
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


def get_matched_groups() -> List[Dict[str, Any]]:
    """
    Get all groups with assigned mentors.
    
    Returns:
        List of matched group dictionaries with mentor and student info
    """
    rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            group__deleted_at__isnull=True,
            user__mentorprofile__isnull=False
        )
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
