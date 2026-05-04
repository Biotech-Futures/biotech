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


# Demo data for testing (referenced from demo.py - configure as needed)
DEMO_MATCHED_GROUPS = []
DEMO_GROUPS = []
DEMO_MENTORS = []


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
    if timezone.now().hour > 0:  # Replace with environment check
        # Use demo data if configured
        matched_group_ids = set(g['group_id'] for g in DEMO_MATCHED_GROUPS)
        unmatched_demo_groups = [g for g in DEMO_GROUPS if g['group_id'] not in matched_group_ids]
        # Call algorithm: return matchMentors(unmatched_demo_groups, DEMO_MENTORS, mode)
        return []
    
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
            group_id=F('id'),
            group_name=F('group_name'),
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
            group_id=F('group_id'),
            interest=F('user__userinterest__interest__interest_desc'),
        )
    )
    
    interests_by_group = _group_interests_by_key(
        [r for r in member_interest_rows if r['interest']],
        'group_id',
        'interest'
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
            'group_id': g['group_id'],
            'group_name': g['group_name'],
            'track_code': g['group_track_code'],
            'student_interests': interests_by_group.get(g['group_id'], []),
            'student_count': member_count_by_group.get(g['group_id'], 0),
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
            mentor_id=F('user_id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            institution=F('institution'),
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
            interest=F('interest__interest_desc'),
        )
    ) if mentor_ids else []
    
    interests_by_mentor = _group_interests_by_key(mentor_interest_rows, 'key', 'interest')
    
    # Build mentor sources
    mentor_sources = [
        {
            'mentor_id': m['mentor_id'],
            'first_name': m['first_name'],
            'last_name': m['last_name'],
            'institution': m['institution'],
            'track_code': m['track_code'],
            'interests': interests_by_mentor.get(m['mentor_id'], []),
            'max_group_count': m['max_grp_cnt'],
            'current_accepted_count': accepted_count_by_mentor.get(m['mentor_id'], 0),
        }
        for m in mentor_rows
    ]
    
    # Run matching algorithm (external call)
    # recommendations = matchMentors(group_sources, mentor_sources, mode)
    recommendations = []
    
    # Save match run
    MatchRun.objects.create(
        initiated_by_user_id=int(admin_user_id),
        run_type='mentor-match',
        rules_snapshot=group_sources,
    )
    
    return recommendations


def get_mentors() -> List[Dict[str, Any]]:
    """
    Get all active mentors with their assignment info.
    
    Returns:
        List of mentor dictionaries
    """
    if timezone.now().hour > 0:  # Replace with environment check
        return [
            {
                'mentor_id': m['mentor_id'],
                'name': f"{m['first_name']} {m['last_name']}".strip(),
                'track_code': m['track_code'],
                'institution': m['institution'],
                'interests': m['interests'],
                'max_group_count': m['max_group_count'],
                'current_accepted_count': m['current_accepted_count'],
                'remaining_capacity': m['max_group_count'] - m['current_accepted_count'],
            }
            for m in DEMO_MENTORS
        ]
    
    # Count accepted assignments per mentor
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
            mentor_id=F('user_id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            institution=F('institution'),
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
            interest=F('interest__interest_desc'),
        )
    ) if mentor_ids else []
    
    interests_by_mentor = _group_interests_by_key(mentor_interest_rows, 'key', 'interest')
    
    result = []
    for m in mentor_rows:
        mentor_id = m['mentor_id']
        current_accepted_count = accepted_count_by_mentor.get(mentor_id, 0)
        result.append({
            'mentor_id': mentor_id,
            'name': f"{m['first_name']} {m['last_name']}".strip(),
            'track_code': m['track_code'],
            'institution': m['institution'],
            'interests': interests_by_mentor.get(mentor_id, []),
            'max_group_count': m['max_grp_cnt'],
            'current_accepted_count': current_accepted_count,
            'remaining_capacity': m['max_grp_cnt'] - current_accepted_count,
        })
    
    return result


def get_unmatched_groups() -> List[Dict[str, Any]]:
    """
    Get all groups without mentors.
    
    Returns:
        List of unmatched group dictionaries
    """
    if timezone.now().hour > 0:  # Replace with environment check
        matched_group_ids = set(g['group_id'] for g in DEMO_MATCHED_GROUPS)
        return [
            {
                'group_id': g['group_id'],
                'group_name': g['group_name'],
                'track_code': g['track_code'],
                'student_interests': g['student_interests'],
                'student_count': g['student_count'],
                'students': g.get('students', []),
            }
            for g in DEMO_GROUPS
            if g['group_id'] not in matched_group_ids
        ]
    
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
            group_id=F('id'),
            group_name=F('group_name'),
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
            group_id=F('group_id'),
            user_id=F('user_id'),
            interest=F('user__userinterest__interest__interest_desc'),
        )
    )
    
    interests_by_group = {}
    interests_by_user = {}
    for row in member_interest_rows:
        if row['interest']:
            if row['group_id'] not in interests_by_group:
                interests_by_group[row['group_id']] = []
            interests_by_group[row['group_id']].append(row['interest'])
            if row['user_id'] not in interests_by_user:
                interests_by_user[row['user_id']] = []
            interests_by_user[row['user_id']].append(row['interest'])
    
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
            group_id=F('group_id'),
            user_id=F('user_id'),
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
            'group_id': g['group_id'],
            'group_name': g['group_name'],
            'track_code': g['track_code'],
            'student_interests': interests_by_group.get(g['group_id'], []),
            'student_count': len(group_students),
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
    if timezone.now().hour > 0:  # Replace with environment check
        return DEMO_MATCHED_GROUPS
    
    rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            group__deleted_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .select_related('group', 'group__track', 'user')
        .values(
            membership_id=F('id'),
            group_id=F('group_id'),
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
            group_id=F('group_id'),
            user_id=F('user_id'),
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
            group_id=F('group_id'),
            user_id=F('user_id'),
            interest=F('user__userinterest__interest__interest_desc'),
        )
    )
    
    interests_by_user = {}
    for row in member_interest_rows:
        if row['interest']:
            if row['user_id'] not in interests_by_user:
                interests_by_user[row['user_id']] = []
            interests_by_user[row['user_id']].append(row['interest'])
    
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
            'membership_id': r['membership_id'],
            'group_id': r['group_id'],
            'group_name': r['group_name'],
            'track_code': track_name_by_id.get(r['group_track_id'], ''),
            'student_count': len(students),
            'students': students,
            'mentor': {
                'mentor_id': r['mentor_id'],
                'name': f"{r['mentor_first_name']} {r['mentor_last_name']}".strip(),
                'is_active': r['is_active'],
                'track_code': track_name_by_id.get(r['mentor_track_id'], '') if r['mentor_track_id'] else '',
                'institution': r['institution'],
            },
        })
    
    return result


def replace_mentor(input_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Replace a mentor in a group with a new one.
    
    Args:
        input_data: Dictionary with membership_id, group_id, and new_mentor_user_id
        
    Returns:
        Dictionary with 'replaced' count
    """
    if timezone.now().hour > 0:  # Replace with environment check
        idx = next(
            (i for i, g in enumerate(DEMO_MATCHED_GROUPS) if g['membership_id'] == input_data['membership_id']),
            -1
        )
        if idx == -1:
            return {'replaced': 0}
        
        new_mentor = next((m for m in DEMO_MENTORS if m['mentor_id'] == input_data['new_mentor_user_id']), None)
        if not new_mentor:
            return {'replaced': 0}
        
        DEMO_MATCHED_GROUPS[idx] = {
            **DEMO_MATCHED_GROUPS[idx],
            'mentor': {
                'mentor_id': new_mentor['mentor_id'],
                'name': f"{new_mentor['first_name']} {new_mentor['last_name']}".strip(),
                'is_active': True,
                'track_code': new_mentor['track_code'],
                'institution': new_mentor['institution'],
            }
        }
        return {'replaced': 1}
    
    # Mark old mentor as left
    GroupMembership.objects.filter(
        id=input_data['membership_id'],
        group_id=input_data['group_id'],
        left_at__isnull=True,
    ).update(left_at=timezone.now())
    
    # Add new mentor
    GroupMembership.objects.create(
        group_id=input_data['group_id'],
        user_id=input_data['new_mentor_user_id'],
        membership_role='mentor',
        joined_at=timezone.now(),
    )
    
    return {'replaced': 1}


def bulk_replace_inactive_mentors() -> Dict[str, int]:
    """
    Replace all inactive mentors with removal from groups.
    
    Returns:
        Dictionary with 'removed_count' of inactive mentor assignments
    """
    if timezone.now().hour > 0:  # Replace with environment check
        before = len(DEMO_MATCHED_GROUPS)
        DEMO_MATCHED_GROUPS[:] = [g for g in DEMO_MATCHED_GROUPS if g['mentor']['is_active']]
        return {'removed_count': before - len(DEMO_MATCHED_GROUPS)}
    
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
        return {'removed_count': 0}
    
    # Mark as left
    count = GroupMembership.objects.filter(
        id__in=[r['id'] for r in inactive_rows],
    ).update(left_at=timezone.now())
    
    return {'removed_count': count}


def confirm_mentor_assignments(input_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Confirm and finalize mentor assignments to groups.
    
    Args:
        input_data: Dictionary with 'assignments' list containing group-mentor mappings
        
    Returns:
        Dictionary with 'confirmed_count' of assignments
    """
    assignments = input_data.get('assignments', [])
    
    if not assignments:
        return {'confirmed_count': 0}
    
    # Deduplicate by group
    unique_by_group = {}
    for item in assignments:
        unique_by_group[item['group_id']] = item['mentor_user_id']
    
    assignments = [
        {'group_id': gid, 'mentor_user_id': mid}
        for gid, mid in unique_by_group.items()
    ]
    
    if timezone.now().hour > 0:  # Replace with environment check
        max_id = max((g['membership_id'] for g in DEMO_MATCHED_GROUPS), default=1000)
        next_id = max_id + 1
        confirmed_count = 0
        
        for item in assignments:
            group = next((g for g in DEMO_GROUPS if g['group_id'] == item['group_id']), None)
            mentor = next((m for m in DEMO_MENTORS if m['mentor_id'] == item['mentor_user_id']), None)
            
            if not group or not mentor:
                continue
            
            DEMO_MATCHED_GROUPS[:] = [g for g in DEMO_MATCHED_GROUPS if g['group_id'] != item['group_id']]
            DEMO_MATCHED_GROUPS.append({
                'membership_id': next_id,
                'group_id': group['group_id'],
                'group_name': group['group_name'],
                'track_code': group['track_code'],
                'student_count': group['student_count'],
                'students': group.get('students', []),
                'mentor': {
                    'mentor_id': mentor['mentor_id'],
                    'name': f"{mentor['first_name']} {mentor['last_name']}".strip(),
                    'is_active': True,
                    'track_code': mentor['track_code'],
                    'institution': mentor['institution'],
                }
            })
            next_id += 1
            confirmed_count += 1
        
        return {'confirmed_count': confirmed_count}
    
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
            membership_role='mentor',
            joined_at=now,
        )
        for a in assignments
    ]
    
    GroupMembership.objects.bulk_create(memberships)
    
    return {'confirmed_count': len(assignments)}


def unassign_mentors(group_ids: List[int]) -> Dict[str, int]:
    """
    Remove mentor assignments from groups.
    
    Args:
        group_ids: List of group IDs to unassign mentors from
        
    Returns:
        Dictionary with 'unassigned_count' of removed assignments
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
        return {'unassigned_count': 0}
    
    count = GroupMembership.objects.filter(
        id__in=[r['id'] for r in mentor_rows]
    ).update(left_at=timezone.now())
    
    return {'unassigned_count': count}