from typing import List, Dict, Any, Optional
from datetime import datetime
from django.db.models import Q, Count, F, Max, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone

from apps.groups.models import Groups, GroupMembership, Tracks
from apps.users.models import User, MentorProfile
from apps.chat.models import Messages
from apps.users.models import UserInterest, AreasOfInterest


def get_mentor_list() -> List[Dict[str, Any]]:
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
    mentor_rows = (
        MentorProfile.objects
        .select_related('user', 'user__track')
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