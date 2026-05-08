from typing import Optional, List
from apps.users.models.admin_scope import AdminScope


def get_admin_track_ids(user) -> Optional[List[int]]:
    """
    Returns None  → Global Admin, no track filter needed.
    Returns list  → Track Admin, restrict to these track IDs (plus NULL-track data).
    """
    if not user or not user.is_authenticated:
        return []

    if AdminScope.objects.filter(user=user, is_global=True).exists():
        return None

    return list(
        AdminScope.objects.filter(user=user, track__isnull=False)
        .values_list('track_id', flat=True)
    )
