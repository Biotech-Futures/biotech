import uuid
from typing import List, Dict, Any, Optional, Set, Tuple
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
from apps.groups.models import Countries, CountryStates
from apps.common.tz import utc_offset_hours
from apps.admin.algorithms.student import (
    build_groups,
    format_recommendation_input,
    recommend_groups_by_country,
    score_student_for_existing_group,
)
from apps.groups.services import sync_supervisor_memberships_for_student


DEFAULT_GROUP_MAX_SIZE = 5


def _read_assignment_value(item: Dict[str, Any], camel_key: str, snake_key: str) -> Any:
    if camel_key in item:
        return item[camel_key]
    return item.get(snake_key)


def _normalize_confirm_assignments(raw_assignments: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_assignments, list):
        raise ValidationError({"assignments": "Expected a list of assignment objects."})

    normalized = []
    errors = {}
    for index, item in enumerate(raw_assignments):
        if not isinstance(item, dict):
            errors[index] = "Expected an assignment object."
            continue

        raw_student_id = _read_assignment_value(item, "studentId", "student_id")
        raw_group_id = _read_assignment_value(item, "groupId", "group_id")
        try:
            student_id = int(raw_student_id)
        except (TypeError, ValueError):
            errors[index] = {"studentId": "Expected an integer student ID."}
            continue

        if student_id <= 0:
            errors[index] = {"studentId": "Expected a positive student ID."}
            continue

        if isinstance(raw_group_id, str) and raw_group_id.startswith("new-"):
            group_id = raw_group_id
        else:
            try:
                group_id = int(raw_group_id)
            except (TypeError, ValueError):
                errors[index] = {
                    "groupId": "Expected an integer group ID or new-* synthetic group ID."
                }
                continue

            if group_id <= 0:
                errors[index] = {"groupId": "Expected a positive group ID."}
                continue

        normalized.append({"student_id": student_id, "group_id": group_id})

    if errors:
        raise ValidationError({"assignments": errors})

    return normalized


class MatchRecommendationGroup:
    """Type definition for recommended group"""
    def __init__(self):
        self.id = None
        self.group_name = None
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


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _without_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _map_existing_students(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        _without_none({
            'id': student.get('id'),
            'name': student.get('name') or f"Student #{student.get('id')}",
            'country': student.get('country'),
            'yearLevel': student.get('yearLevel') or student.get('yearlevel'),
            'interests': student.get('interests') or [],
        })
        for student in group.get('groupStudent', [])
    ]


def _map_recommended_student(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'student': recommendation['student'],
        'reason': recommendation['reason'],
        'score': recommendation['score'],
        'scoreBreakdown': recommendation['scoreBreakdown'],
    }


def _group_student_recommendations(
    recommendations: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    groups_by_id = {}
    unmatched_students = []

    for recommendation in recommendations:
        group = recommendation.get('recommendGroup')
        if not group:
            unmatched_students.append(_map_recommended_student(recommendation))
            continue

        group_key = str(group.get('id'))
        grouped = groups_by_id.get(group_key)
        if not grouped:
            grouped = {
                'id': group.get('id'),
                'groupName': group.get('groupName'),
                'maxSize': group.get('maxSize') or DEFAULT_GROUP_MAX_SIZE,
                'tutor': group.get('tutor'),
                'existingStudents': _map_existing_students(group),
                'recommendStudents': [],
            }
            groups_by_id[group_key] = grouped

        grouped['recommendStudents'].append(_map_recommended_student(recommendation))

    groups = sorted(groups_by_id.values(), key=lambda group: str(group['id']))
    for group in groups:
        group['recommendStudents'].sort(
            key=lambda item: str(item['student']['id'])
        )
    unmatched_students.sort(key=lambda item: str(item['student']['id']))

    return {'groups': groups, 'unmatchedStudents': unmatched_students}


def _build_form_recommendations(
    students: List[Dict[str, Any]],
    grouped_result: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    objective_by_student_id = {}
    score_by_student_id = {
        str(item['studentId']): item
        for item in grouped_result.get('studentScores', [])
    }
    unmatched_by_student_id = {
        str(item['studentId']): item
        for item in grouped_result.get('unmatchedStudentReasons', [])
    }
    group_by_student_id = {}

    for group in grouped_result.get('groups', []):
        for student_id in group.get('studentIds', []):
            sid = str(student_id)
            group_by_student_id[sid] = group
            objective_by_student_id[sid] = group['scoreBreakdown']['objectiveScore']

    for student in students:
        objective_by_student_id.setdefault(str(student['id']), 0)

    recommendations = []
    for student in students:
        sid = str(student['id'])
        matched_group = group_by_student_id.get(sid)

        if not matched_group:
            unmatched = unmatched_by_student_id.get(sid)
            recommendations.append({
                'student': student,
                'recommendGroup': None,
                'reason': unmatched['reason'] if unmatched else 'No valid 2-5 member score-based group found for this student.',
                'score': 0,
                'scoreBreakdown': {
                    'baseScore': 100,
                    'yearPenalty': 0,
                    'countryPenalty': 0,
                    'timezonePenalty': 0,
                    'sizeBonus': 0,
                    'totalPenalty': 100,
                    'objectiveScore': 0,
                },
            })
            continue

        student_score = score_by_student_id.get(sid)
        group_country = matched_group['country'] or 'group'
        virtual_group_id = f"new-{group_country}-{'-'.join(str(item) for item in matched_group['studentIds'])}"
        recommendations.append({
            'student': student,
            'recommendGroup': {
                'id': virtual_group_id,
                'groupName': "Suggested Group",
                'maxSize': DEFAULT_GROUP_MAX_SIZE,
                'tutor': None,
                'groupStudent': [],
            },
            'reason': 'Assigned to highest score-based formed group considering interests, country, and compatibility.',
            'score': student_score['score'] if student_score else matched_group['groupScore'],
            'scoreBreakdown': {
                'baseScore': student_score['scoreBreakdown']['baseScore'] if student_score else 100,
                'yearPenalty': student_score['scoreBreakdown']['yearPenalty'] if student_score else 0,
                'countryPenalty': student_score['scoreBreakdown']['countryPenalty'] if student_score else 0,
                'timezonePenalty': student_score['scoreBreakdown']['timezonePenalty'] if student_score else 0,
                'sizeBonus': matched_group['scoreBreakdown']['sizeBonus'],
                'totalPenalty': student_score['scoreBreakdown']['totalPenalty'] if student_score else 100,
                'objectiveScore': matched_group['scoreBreakdown']['objectiveScore'],
            },
        })

    recommendations.sort(key=lambda item: str(item['student']['id']))
    return recommendations, objective_by_student_id


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
        .select_related('user', 'user__country')
        .values(
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            year_level=F('year_lvl'),
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )

    # Query students in groups
    group_members_rows = (
        GroupMembership.objects
        .filter(
            left_at__isnull=True,
            user__studentprofile__isnull=False
        )
        .select_related('group', 'user', 'user__country')
        .values(
            'group_id',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            year_level=F('user__studentprofile__year_lvl'),
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )

    group_ids = list(set(row['group_id'] for row in group_members_rows))

    # Get group metadata
    group_meta_rows = (
        Groups.objects
        .filter(id__in=group_ids, deleted_at__isnull=True)
        .values(
            'group_name',
            group_id=F('id'),
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
    
    group_students = []
    for student in group_members_rows:
        group_meta = group_meta_by_id.get(student['group_id'])
        if not group_meta:
            continue

        tutor = tutor_by_group_id.get(student['group_id'])
        group_students.append({
            **student,
            'group_name': group_meta['group_name'],
            'group_tutor_id': tutor['tutor_user_id'] if tutor else None,
            'group_tutor_name': tutor['tutor_name'] if tutor else None,
        })

    formatted_individual_students = [
        {
            **student,
            'interests': interests_by_user.get(student['user_id'], []),
        }
        for student in standalone_students
    ]
    formatted_group_students = [
        {
            **student,
            'interests': interests_by_user.get(student['user_id'], []),
        }
        for student in group_students
    ]

    ungrouped_students = [
        _without_none({
            'id': student['user_id'],
            'name': f"{student['first_name'] or ''} {student['last_name'] or ''}".strip(),
            'country': student['country_name'],
            'timezoneOffsetHours': utc_offset_hours(student['user_tz']),
            'yearLevel': _safe_int(student['year_level']),
            'interests': interests_by_user.get(student['user_id'], []),
        })
        for student in formatted_individual_students
        if student.get('user_id') is not None
    ]

    join_input = format_recommendation_input(
        [
            {
                'userId': student['user_id'],
                'firstName': student['first_name'],
                'lastName': student['last_name'],
                'countryName': student['country_name'],
                'timezoneOffsetHours': utc_offset_hours(student['user_tz']),
                'yearLevel': _safe_int(student['year_level']),
                'interests': student.get('interests', []),
                'groupId': student['group_id'],
                'groupName': student['group_name'],
                'groupTutorId': student['group_tutor_id'],
                'groupTutorName': student['group_tutor_name'],
            }
            for student in formatted_group_students
        ],
        [
            {
                'userId': student['user_id'],
                'firstName': student['first_name'],
                'lastName': student['last_name'],
                'countryName': student['country_name'],
                'timezoneOffsetHours': utc_offset_hours(student['user_tz']),
                'yearLevel': _safe_int(student['year_level']),
                'interests': student.get('interests', []),
            }
            for student in formatted_individual_students
        ],
    )
    join_recommendations = recommend_groups_by_country(join_input)

    baseline_form = build_groups(ungrouped_students)
    _, baseline_objective_by_student_id = _build_form_recommendations(
        ungrouped_students,
        baseline_form,
    )

    available_seats_by_group_id = {}
    for recommendation in join_recommendations:
        group = recommendation.get('recommendGroup')
        if not group:
            continue

        group_key = str(group['id'])
        if group_key in available_seats_by_group_id:
            continue

        max_size = group.get('maxSize') or DEFAULT_GROUP_MAX_SIZE
        existing_count = len(group.get('groupStudent', []))
        available_seats_by_group_id[group_key] = max(0, max_size - existing_count)

    join_candidates = []
    for recommendation in join_recommendations:
        group = recommendation.get('recommendGroup')
        if not group:
            continue

        student_id = str(recommendation['student']['id'])
        join_objective = recommendation['scoreBreakdown']['objectiveScore']
        form_objective = baseline_objective_by_student_id.get(student_id, 0)
        join_candidates.append({
            'recommendation': recommendation,
            'student_id': student_id,
            'group_id': str(group['id']),
            'join_objective': join_objective,
            'form_objective': form_objective,
            'delta': join_objective - form_objective,
        })

    join_candidates.sort(
        key=lambda item: (
            -item['delta'],
            -item['join_objective'],
            item['student_id'],
        )
    )

    selected_join_student_ids = set()
    for candidate in join_candidates:
        if candidate['delta'] <= 0:
            continue
        if candidate['student_id'] in selected_join_student_ids:
            continue
        remaining_seats = available_seats_by_group_id.get(candidate['group_id'], 0)
        if remaining_seats <= 0:
            continue

        selected_join_student_ids.add(candidate['student_id'])
        available_seats_by_group_id[candidate['group_id']] = remaining_seats - 1

    form_pool = [
        student
        for student in ungrouped_students
        if str(student['id']) not in selected_join_student_ids
    ]
    final_form = build_groups(form_pool)
    final_form_recommendations, _ = _build_form_recommendations(form_pool, final_form)

    selected_join_recommendations = [
        candidate['recommendation']
        for candidate in join_candidates
        if candidate['student_id'] in selected_join_student_ids
    ]
    flat_recommendations = sorted(
        selected_join_recommendations + final_form_recommendations,
        key=lambda item: str(item['student']['id']),
    )
    grouped_recommendations = _group_student_recommendations(flat_recommendations)

    # Get all groups for not-full-groups report
    all_groups = (
        Groups.objects
        .filter(deleted_at__isnull=True)
        .values(
            'group_name',
            group_id=F('id'),
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
    for row in active_student_rows:
        group_id = row['group_id']
        if group_id not in students_by_group:
            students_by_group[group_id] = []
        students_by_group[group_id].append({
            'id': row['user_id'],
            'name': f"{row['first_name']} {row['last_name']}".strip(),
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
                'maxSize': DEFAULT_GROUP_MAX_SIZE,
                'tutor': tutor,
                'groupStudent': group_students,
                'studentCount': student_count,
                'availableSeats': available_seats,
            })
    
    # Save match run
    MatchRun.objects.create(
        initiated_by_user_id=int(uid),
        run_type='student-match',
        rules_snapshot={
            'strategy': 'hybrid-join-or-form',
            'studentCount': len(ungrouped_students),
            'joinInput': join_input,
            'baselineForm': baseline_form,
            'finalForm': final_form,
            'selectedJoinStudentIds': list(selected_join_student_ids),
        }
    )
    
    result = MatchStudentResult()
    result.recommendations = grouped_recommendations['groups']
    result.unmatched_students = grouped_recommendations['unmatchedStudents']
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
        .select_related('user', 'user__country')
        .values(
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            year_level=F('year_lvl'),
            country_name=F('user__country__country_name'),
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


def recommend_students_for_group(group_id: int) -> Dict[str, Any]:
    """Rank standalone students to fill a seat in a given group.

    Scores every student not in any active group against the target group with the
    same criteria as auto-matching (a shared interest is required; year/country/
    timezone proximity improve the score). Returns candidates best-first with their
    score and shared interests. Empty when the group is full, has no student members
    to compare against, or no standalone student shares an interest.
    """
    try:
        group = Groups.objects.get(id=group_id, deleted_at__isnull=True)
    except Groups.DoesNotExist:
        return {"msg": "Group not found", "data": None}

    member_rows = list(
        GroupMembership.objects
        .filter(group_id=group_id, left_at__isnull=True, user__studentprofile__isnull=False)
        .select_related('user', 'user__country')
        .values(
            'user_id',
            year_level=F('user__studentprofile__year_lvl'),
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )

    active_membership_subquery = GroupMembership.objects.filter(
        user_id=OuterRef('user_id'), left_at__isnull=True
    )
    standalone = list(
        StudentProfile.objects
        .filter(~Exists(active_membership_subquery))
        .select_related('user', 'user__country')
        .values(
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            year_level=F('year_lvl'),
            country_name=F('user__country__country_name'),
            user_tz=F('user__timezone'),
        )
    )

    interests_by_user = _map_interests_by_user_id(
        UserInterest.objects
        .filter(user_id__in=[r['user_id'] for r in member_rows] + [s['user_id'] for s in standalone])
        .select_related('interest')
        .values('user_id', interest_desc=F('interest__interest_desc'))
    )

    group_input = {
        'id': group.id,
        'groupName': group.group_name,
        'maxSize': DEFAULT_GROUP_MAX_SIZE,
        'groupStudent': [
            {
                'id': r['user_id'],
                'country': r['country_name'],
                'timezoneOffsetHours': utc_offset_hours(r['user_tz']),
                'yearLevel': _safe_int(r['year_level']),
                'interests': interests_by_user.get(r['user_id'], []),
            }
            for r in member_rows
        ],
    }

    suggestions = []
    for s in standalone:
        student_input = {
            'id': s['user_id'],
            'name': f"{s['first_name'] or ''} {s['last_name'] or ''}".strip(),
            'country': s['country_name'],
            'timezoneOffsetHours': utc_offset_hours(s['user_tz']),
            'yearLevel': _safe_int(s['year_level']),
            'interests': interests_by_user.get(s['user_id'], []),
        }
        candidate = score_student_for_existing_group(student_input, group_input)
        if candidate is None:
            continue
        suggestions.append({
            'studentUserId': s['user_id'],
            'name': student_input['name'],
            'yearLevel': student_input['yearLevel'],
            'country': s['country_name'],
            'score': candidate['scoreBreakdown']['objectiveScore'],
            'sharedInterests': candidate['sharedInterests'],
        })

    suggestions.sort(key=lambda x: (-x['score'], x['name']))

    return {
        "msg": "Student suggestions computed",
        "data": {
            "groupId": group.id,
            "groupName": group.group_name,
            "isFull": len(member_rows) >= DEFAULT_GROUP_MAX_SIZE,
            "suggestions": suggestions,
        },
    }


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
    
    assignments = _normalize_confirm_assignments(assignments)
    
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
            # Collect synthetic group IDs in first-seen order.
            synthetic_ids: Dict[str, bool] = {}
            for item in assignments:
                gid = item['group_id']
                if isinstance(gid, str) and gid.startswith('new-'):
                    synthetic_ids.setdefault(gid, True)

            # Create one new group per synthetic ID. Seed with a unique
            # placeholder so the create never collides with an existing active
            # group literally named "Auto Group" (group names are globally
            # unique now), then rename to the stable pk-based name.
            created_group_by_synthetic = {}
            for synthetic_id in synthetic_ids:
                group = Groups.objects.create(group_name=f'Auto Group {uuid.uuid4()}')
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
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )
            for a in resolved_assignments
            if isinstance(a['group_id'], int)
        ]
        
        if memberships:
            GroupMembership.objects.bulk_create(memberships)
            for student_id in [m.user_id for m in memberships]:
                sync_supervisor_memberships_for_student(student_id)

    return {'assigned_count': len(resolved_assignments)}
