from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from django.db.models import Q, Count, F, Max, Value, CharField, Exists, OuterRef
from django.db.models.functions import Concat
from django.utils import timezone
from django.db import transaction

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.users.models import User, MentorProfile, StudentProfile
from apps.users.models import UserInterest, AreasOfInterest
from apps.matching_runtime.models import MatchRun
from apps.groups.models import Countries, CountryStates


DEFAULT_GROUP_MAX_SIZE = 5


class MatchRecommendationGroup:
    """Type definition for recommended group"""
    def __init__(self):
        self.id = None
        self.group_name = None
        self.track_id = None
        self.max_size = None
        self.tutor = None
        self.existing_students = []
        self.recommend_students = []


class MatchStudentResult:
    """Type definition for match result"""
    def __init__(self):
        self.recommendations = []
        self.unmatched_students = []
        self.not_full_groups = []


def _map_interests_by_user_id(rows: List[Dict]) -> Dict[int, List[str]]:
    """Group interests by user ID"""
    interests_by_user = {}
    for row in rows:
        user_id = row['user_id']
        if user_id not in interests_by_user:
            interests_by_user[user_id] = []
        interests_by_user[user_id].append(row['interest_desc'])
    return interests_by_user


def match_student(uid: str) -> MatchStudentResult:
    """
    Run student matching algorithm combining join-or-form strategy.
    
    Args:
        uid: Admin user ID initiating the match
        
    Returns:
        MatchStudentResult with recommendations, unmatched students, and available groups
    """
    # Query standalone students (not in any active group)
    active_membership_subquery = GroupMembership.objects.filter(
        user_id=OuterRef('user_id'),
        left_at__isnull=True
    )
    
    standalone_students = (
        StudentProfile.objects
        .filter(~Exists(active_membership_subquery))
        .select_related('user', 'user__track', 'user__track__state')
        .annotate(
            country_state_id=F('user__track__state_id'),
        )
        .values(
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            track_id=F('user__track_id'),
            track_code=F('user__track__track_name'),
            year_level=F('year_lvl'),
            country_name=F('user__track__state__country__country_name'),
        )
    )

    # Query students in groups
    group_members_rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('group', 'user', 'user__track')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            track_id=F('user__track_id'),
            track_code=F('user__track__track_name'),
            year_level=F('user__studentprofile__year_lvl'),
            country_name=F('user__track__state__country__country_name'),
        )
    )
    
    group_ids = list(set(row['group_id'] for row in group_members_rows))
    
    # Get group metadata
    group_meta_rows = (
        Groups.objects
        .filter(id__in=group_ids, deleted_at__isnull=True)
        .select_related('track')
        .values(
            'group_name',
            group_id=F('id'),
            group_track_id=F('track_id'),
            group_track_code=F('track__track_name'),
        )
    )
    
    group_meta_by_id = {row['group_id']: row for row in group_meta_rows}
    
    # Get mentors for groups
    group_mentor_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=group_ids,
            left_at__isnull=True,
            user__mentorprofile__isnull=False
        )
        .select_related('group', 'user')
        .values(
            'group_id',
            tutor_user_id=F('user_id'),
            tutor_first_name=F('user__first_name'),
            tutor_last_name=F('user__last_name'),
        )
    )
    
    tutor_by_group_id = {}
    for row in group_mentor_rows:
        if row['group_id'] not in tutor_by_group_id:
            tutor_by_group_id[row['group_id']] = {
                'tutor_user_id': row['tutor_user_id'],
                'tutor_name': f"{row['tutor_first_name']} {row['tutor_last_name']}".strip(),
            }
    
    # Get user interests
    all_user_ids = set(
        list(row['user_id'] for row in standalone_students) +
        list(row['user_id'] for row in group_members_rows)
    )
    
    interest_rows = (
        UserInterest.objects
        .filter(user_id__in=all_user_ids)
        .select_related('interest')
        .values(
            'user_id',
            interest_desc=F('interest__interest_desc'),
        )
    )
    
    interests_by_user = _map_interests_by_user_id(interest_rows)
    
    # Get all groups for not-full-groups report
    all_groups = (
        Groups.objects
        .filter(deleted_at__isnull=True)
        .select_related('track')
        .values(
            'group_name',
            'track_id',
            group_id=F('id'),
            track_code=F('track__track_name'),
        )
    )
    
    all_group_ids = [g['group_id'] for g in all_groups]
    
    # Count active students per group
    active_student_rows = (
        GroupMembership.objects
        .filter(
            group_id__in=all_group_ids,
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('user', 'user__track')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            track_code=F('user__track__track_name'),
            country_name=F('user__track__state__country__country_name'),
        )
    )

    students_by_group = {}
    for row in active_student_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'id': row['user_id'],
            'name': f"{row['first_name']} {row['last_name']}".strip(),
            'track_id': row['track_code'],
            'country': row['country_name'],
            'interests': interests_by_user.get(row['user_id'], []),
        })
    
    # Build not-full groups
    not_full_groups = []
    for group in all_groups:
        group_students = students_by_group.get(group['group_id'], [])
        student_count = len(group_students)
        available_seats = max(0, DEFAULT_GROUP_MAX_SIZE - student_count)
        
        if available_seats > 0:
            tutor = tutor_by_group_id.get(group['group_id'])
            not_full_groups.append({
                'id': group['group_id'],
                'groupName': group['group_name'],
                'trackId': group['track_code'] or group['track_id'],
                'maxSize': DEFAULT_GROUP_MAX_SIZE,
                'tutor': tutor,
                'groupStudent': group_students,
                'studentCount': student_count,
                'availableSeats': available_seats,
            })
    
    # Save match run
    now = timezone.now().isoformat()
    match_run = MatchRun.objects.create(
        initiated_by_user_id=int(uid),
        run_type='student-match',
        rules_snapshot={
            'strategy': 'hybrid-join-or-form',
            'studentCount': len(list(standalone_students)),
        }
    )
    
    result = MatchStudentResult()
    result.recommendations = []
    result.unmatched_students = []
    result.not_full_groups = not_full_groups
    
    return result


def get_individual_students() -> List[Dict[str, Any]]:
    """
    Get all students not currently in any active group.
    
    Returns:
        List of individual student dictionaries
    """
    active_membership_subquery = GroupMembership.objects.filter(
        user_id=OuterRef('user_id'),
        left_at__isnull=True
    )
    
    individual_students = (
        StudentProfile.objects
        .filter(~Exists(active_membership_subquery))
        .select_related('user', 'user__track')
        .values(
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            track_id=F('user__track_id'),
            track_code=F('user__track__track_name'),
            year_level=F('year_lvl'),
            country_name=F('user__track__state__country__country_name'),
        )
    )
    
    user_ids = [s['user_id'] for s in individual_students]
    
    interest_rows = (
        UserInterest.objects
        .filter(user_id__in=user_ids)
        .select_related('interest')
        .values(
            'user_id',
            interest_desc=F('interest__interest_desc'),
        )
    )
    
    interests_by_user = _map_interests_by_user_id(interest_rows)
    
    result = []
    for student in individual_students:
        student['interests'] = interests_by_user.get(student['user_id'], [])
        result.append(student)
    
    return result


def confirm_student_assignments(input_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Confirm and finalize student assignments to groups.
    
    Args:
        input_data: Dictionary with 'assignments' list containing student-group mappings
        
    Returns:
        Dictionary with 'assigned_count' of successful assignments
    """
    assignments = input_data.get('assignments', [])
    
    if not assignments:
        return {'assigned_count': 0}
    
    # Deduplicate by student
    unique_by_student = {}
    for item in assignments:
        unique_by_student[item['student_id']] = item['group_id']
    
    assignments = [
        {'student_id': sid, 'group_id': gid}
        for sid, gid in unique_by_student.items()
    ]
    
    student_ids = [a['student_id'] for a in assignments]
    now = timezone.now()
    
    with transaction.atomic():
        # Remove existing memberships
        GroupMembership.objects.filter(user_id__in=student_ids).delete()
        
        # Handle synthetic groups (new groups starting with "new-")
        resolved_assignments = assignments
        
        if any(isinstance(a['group_id'], str) and a['group_id'].startswith('new-') for a in assignments):
            # Get student track IDs for new group creation
            students = User.objects.filter(id__in=student_ids).values('id', 'track_id')
            track_by_student = {s['id']: s['track_id'] for s in students}
            
            # Group by synthetic ID
            synthetic_groups = {}
            for item in assignments:
                if isinstance(item['group_id'], str) and item['group_id'].startswith('new-'):
                    if item['group_id'] not in synthetic_groups:
                        synthetic_groups[item['group_id']] = []
                    synthetic_groups[item['group_id']].append(item['student_id'])
            
            # Create new groups
            created_group_by_synthetic = {}
            for synthetic_id, members in synthetic_groups.items():
                first_track = None
                for member_id in members:
                    track_id = track_by_student.get(member_id)
                    if track_id:
                        first_track = track_id
                        break
                
                if first_track is None:
                    continue
                
                group = Groups.objects.create(
                    group_name='Auto Group',
                    track_id=first_track,
                )
                group.group_name = f'Auto Group {group.id}'
                group.save()
                
                created_group_by_synthetic[synthetic_id] = group.id
            
            # Resolve assignments
            resolved_assignments = []
            for item in assignments:
                if isinstance(item['group_id'], str):
                    mapped_id = created_group_by_synthetic.get(item['group_id'])
                    if mapped_id:
                        resolved_assignments.append({
                            'student_id': item['student_id'],
                            'group_id': mapped_id
                        })
                else:
                    resolved_assignments.append(item)
        
        # Create memberships
        memberships = [
            GroupMembership(
                group_id=a['group_id'],
                user_id=a['student_id'],
                joined_at=now,
                membership_role='student',
            )
            for a in resolved_assignments
            if isinstance(a['group_id'], int)
        ]
        
        if memberships:
            GroupMembership.objects.bulk_create(memberships)
    
    return {'assigned_count': len(resolved_assignments)}