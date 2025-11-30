from typing import Optional
from django.utils import timezone
from apps.groups.models import Groups, Tracks

def generate_group_name(track: Tracks, cohort_year: Optional[int] = None) -> str:
    """
    Generate a unique group name for the given Track and cohort_year.

    - Uses the Track's ``track_name`` as the base.
    - Appends a numeric suffix like "-01", "-02", ... to ensure uniqueness among
      ACTIVE groups (deleted_flag=False) within the same (track, cohort_year).
    - Ensures the final name length does not exceed 255 characters.
    - If ``cohort_year`` is not provided, defaults to the current year.

    This is similar to ``get_group_name`` but does not require a ``Groups`` instance.
    """
    if track is None:
        raise ValueError("Track is required to generate a group name.")

    year = cohort_year or timezone.now().year
    base = (getattr(track, "track_name", "") or "").strip() or "Group"

    max_len = 255

    for i in range(1, 1000):  # up to -999
        suffix = f"-{i:02d}" if i < 100 else f"-{i}"
        allow_base_len = max_len - len(suffix)
        candidate = (base[:allow_base_len]) + suffix

        exists = Groups.objects.filter(
            track=track,
            cohort_year=year,
            deleted_flag=False,
            group_name=candidate,
        ).exists()

        if not exists:
            return candidate

    # Fallback if all 999 numeric suffixes are taken
    fallback_suffix = timezone.now().strftime("-%Y%m%d%H%M%S")
    allow_base_len = max_len - len(fallback_suffix)
    return (base[:allow_base_len]) + fallback_suffix
