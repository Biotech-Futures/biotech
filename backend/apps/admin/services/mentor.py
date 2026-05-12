from typing import List, Dict, Any, Optional
from datetime import datetime
from django.db.models import Q, Count, F, Max, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.users.models import User, MentorProfile
from apps.chat.models import Messages
from apps.users.models import UserInterest, AreasOfInterest
from apps.admin.scope_utils import get_admin_track_ids


def get_mentor_list(requesting_user=None) -> List[Dict[str, Any]]:
    """
    Fetch all mentors with their assignment counts, certificates, interests, and last message info.
    
    Returns:
        List of mentor dictionaries with full profile information
    """
    # 1. Count currently assigned groups per mentor
    assigned_count_rows = (
        GroupMembership.objects
        .filter(left_at__isnull=True)
        .filter(user__mentorprofile__isnull=False)
        .values('user_id')
        .annotate(count=Count('id'))
    )
    
    assigned_count_by_mentor = {
        row['user_id']: row['count'] 
        for row in assigned_count_rows
    }
    
    # 2. Fetch all mentor base info
    mentor_qs = MentorProfile.objects.select_related('user', 'user__track')
    track_ids = get_admin_track_ids(requesting_user)
    if track_ids is not None:
        mentor_qs = mentor_qs.filter(Q(user__track_id__in=track_ids) | Q(user__track__isnull=True))
    mentor_rows = (
        mentor_qs
        .values(
            'institution',
            'user_id',
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            email=F('user__email'),
            is_active=F('user__is_active'),
            max_grp_cnt=F('max_group_count'),
            track_code=F('user__track__track_name'),
            background_desc=F('background'),
        )
        .order_by('user_id')
    )
    
    if not mentor_rows:
        return []
    
    mentor_ids = [m['user_id'] for m in mentor_rows]
    
    # 3. Last message sent by each mentor (excluding deleted messages)
    last_message_rows = (
        Messages.objects
        .filter(
            deleted_at__isnull=True,
            sender_user_id__in=mentor_ids
        )
        .values('sender_user_id')
        .annotate(last_message_at=Max('sent_at'))
    )

    last_message_by_mentor = {
        row['sender_user_id']: row['last_message_at']
        for row in last_message_rows
    }
    
    # 4. Certificates per mentor
    from apps.certificates.models import MentorCertificate, CertificateType
    
    certificate_rows = (
        MentorCertificate.objects
        .filter(mentor_profile_id__in=mentor_ids)
        .select_related('certificate_type')
        .values(
            'mentor_profile_id',
            'certificate_number',
            'issued_by',
            'issued_at',
            'expires_at',
            'file_url',
            'verified',
            certificate_type_name=F('certificate_type__certificate_type'),
        )
    )
    
    certificates_by_mentor = {}
    for row in certificate_rows:
        mentor_id = row['mentor_profile_id']
        if mentor_id not in certificates_by_mentor:
            certificates_by_mentor[mentor_id] = []
        certificates_by_mentor[mentor_id].append({
            'certificateTypeName': row['certificate_type_name'],
            'certificateNumber': row['certificate_number'],
            'issuedBy': row['issued_by'],
            'issuedAt': row['issued_at'],
            'expiresAt': row['expires_at'],
            'fileUrl': row['file_url'],
            'verifiedAt': row['verified'],
        })
    
    # 5. Interests per mentor
    interest_rows = (
        UserInterest.objects
        .filter(user_id__in=mentor_ids)
        .select_related('interest')
        .values(
            'user_id',
            interest_desc=F('interest__interest_desc'),
        )
    )
    
    interests_by_mentor = {}
    for row in interest_rows:
        user_id = row['user_id']
        if user_id not in interests_by_mentor:
            interests_by_mentor[user_id] = []
        interests_by_mentor[user_id].append(row['interest_desc'])
    
    # Build result
    result = []
    for m in mentor_rows:
        mentor_id = m['user_id']
        current_assigned_count = assigned_count_by_mentor.get(mentor_id, 0)
        
        result.append({
            'mentorId': mentor_id,
            'firstName': m['first_name'],
            'lastName': m['last_name'],
            'name': f"{m['first_name']} {m['last_name']}".strip(),
            'email': m['email'],
            'isActive': m['is_active'],
            'institution': m['institution'],
            'trackCode': m['track_code'],
            'maxGroupCount': m['max_grp_cnt'],
            'currentAssignedCount': current_assigned_count,
            'remainingCapacity': m['max_grp_cnt'] - current_assigned_count,
            'interests': interests_by_mentor.get(mentor_id, []),
            'lastMessageAt': last_message_by_mentor.get(mentor_id),
            'availability': [],
            'certificates': certificates_by_mentor.get(mentor_id, []),
        })
    
    return result


def set_mentor_active(mentor_id: int, is_active: bool) -> Dict[str, Any]:
    """
    Set a mentor's active status.
    
    Args:
        mentor_id: The user ID of the mentor
        is_active: Whether to activate or deactivate
        
    Returns:
        Dictionary with mentor_id and is_active status
    """
    User.objects.filter(id=mentor_id).update(is_active=is_active)
    return {'mentorId': mentor_id, 'isActive': is_active}


def count_current_assigned_groups(mentor_id: int) -> int:
    """Count the number of groups currently assigned to a mentor (active memberships only)."""
    return (
        GroupMembership.objects
        .filter(
            user_id=mentor_id,
            left_at__isnull=True,
            user__mentorprofile__isnull=False,
        )
        .count()
    )


def validate_max_group_count_against_assigned(
    mentor_id: int, max_group_count: Any
) -> int:
    """
    Spec §2.6: a mentor's max group count cannot be set below the number of
    groups they are currently assigned to. Raises rest_framework ValidationError
    if the input is invalid or violates the floor.

    Returns the validated integer value on success.
    """
    if isinstance(max_group_count, bool) or not isinstance(max_group_count, int):
        try:
            max_group_count = int(max_group_count)
        except (TypeError, ValueError):
            raise ValidationError({
                "mentorMaxGroupCount": "Max group count must be an integer.",
            })

    if max_group_count < 0:
        raise ValidationError({
            "mentorMaxGroupCount": "Max group count cannot be negative.",
        })

    current_assigned = count_current_assigned_groups(mentor_id)
    if max_group_count < current_assigned:
        raise ValidationError({
            "mentorMaxGroupCount": (
                f"Max group count ({max_group_count}) cannot be below the "
                f"mentor's current assigned group count ({current_assigned})."
            ),
            "currentAssignedCount": current_assigned,
        })

    return max_group_count


def set_mentor_max_group_count(mentor_id: int, max_group_count: Any) -> Dict[str, Any]:
    """
    Update a mentor's max group count. Rejects values below the mentor's
    current assigned group count (Spec §2.6).
    """
    validated = validate_max_group_count_against_assigned(mentor_id, max_group_count)
    updated = MentorProfile.objects.filter(user_id=mentor_id).update(
        max_group_count=validated,
    )
    if updated == 0:
        raise ValidationError({"mentor": "Mentor profile not found."})
    current_assigned = count_current_assigned_groups(mentor_id)
    return {
        "mentorId": mentor_id,
        "maxGroupCount": validated,
        "currentAssignedCount": current_assigned,
        "remainingCapacity": validated - current_assigned,
    }