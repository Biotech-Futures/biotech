"""Track admin service.

Create / archive / restore tracks (global admin only) and list states for the
create form. Track admins can only see their own non-archived tracks; global
admins can opt in to see archived tracks for restoration.

`Tracks.is_archived` is added by the groups team; until that migration is in
place, calls referencing it raise FieldError. That is acceptable because this
feature branch is not merged until the field exists upstream.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, TypedDict

from django.db import transaction
from django.db.models import Q

from apps.admin.scope_utils import get_admin_track_ids
from apps.groups.models import CountryStates, GroupMembership, Tracks
from apps.services.auth_service import terminate_user_sessions
from apps.users.models import User
from apps.users.utils.admin_scope import is_operational_admin

logger = logging.getLogger(__name__)


class CreateTrackInput(TypedDict, total=False):
    track_name: str
    state_id: int


def _serialize(track: Tracks) -> Dict[str, Any]:
    return {
        "id": track.id,
        "trackName": track.track_name,
        "stateId": track.state_id,
        "stateName": track.state.state_name if track.state_id else None,
        "isArchived": getattr(track, "is_archived", False),
    }


def _is_global_admin(user) -> bool:
    return get_admin_track_ids(user) is None


def list_tracks(
    requesting_user=None,
    include_archived: bool = False,
) -> Dict[str, Any]:
    """List tracks visible to the requesting admin.

    - Track admins: only their assigned tracks, archived hidden unconditionally.
    - Global admins: all tracks; archived only if include_archived=True.
    """
    qs = Tracks.objects.select_related("state").all()

    track_ids = get_admin_track_ids(requesting_user)
    is_global = track_ids is None

    if not is_global:
        qs = qs.filter(id__in=track_ids).filter(is_archived=False)
    elif not include_archived:
        qs = qs.filter(is_archived=False)

    tracks = list(qs.order_by("track_name"))
    return {
        "msg": "Tracks retrieved successfully",
        "data": [_serialize(t) for t in tracks],
    }


def create_track(input_data: CreateTrackInput, requesting_user=None) -> Dict[str, Any]:
    if not _is_global_admin(requesting_user):
        return {"msg": "Only global admins can create tracks", "data": None}

    name = (input_data.get("track_name") or "").strip()
    if not name:
        return {"msg": "Track name is required", "data": None}

    state_id = input_data.get("state_id")
    if not state_id:
        return {"msg": "State is required", "data": None}

    if not CountryStates.objects.filter(id=state_id).exists():
        return {"msg": "Invalid state", "data": None}

    if Tracks.objects.filter(track_name=name).exists():
        return {"msg": "Track name already exists", "data": None}

    track = Tracks.objects.create(track_name=name, state_id=state_id)
    return {"msg": "Track created successfully", "data": _serialize(track)}


@transaction.atomic
def archive_track(track_id: int, requesting_user=None) -> Dict[str, Any]:
    if not _is_global_admin(requesting_user):
        return {"msg": "Only global admins can archive tracks", "data": None}

    try:
        track = Tracks.objects.get(id=track_id)
    except Tracks.DoesNotExist:
        return {"msg": "Track not found", "data": None}

    track.is_archived = True
    track.save(update_fields=["is_archived"])

    _terminate_sessions_for_archived_track(track)

    return {"msg": "Track archived successfully", "data": _serialize(track)}


def _terminate_sessions_for_archived_track(track: Tracks) -> None:
    """Force-logout every user affected by this track being archived.

    Mirrors the login-time ``is_track_archived`` gate: a user who can no
    longer log in shouldn't be allowed to keep using an existing session
    either. Operational admins are exempt because the login gate exempts
    them too (otherwise an admin archiving their own track would log
    themselves out).

    "Affected" = assigned directly via ``User.track`` OR participating in
    any group that belongs to this track via an active membership
    (``GroupMembership.left_at IS NULL``). Both paths are unioned so we
    catch students/mentors who don't have ``User.track`` set but are
    actively in a track-bound group.
    """
    affected_user_ids = set(
        User.objects.filter(
            Q(track_id=track.id)
            | Q(
                id__in=GroupMembership.objects.filter(
                    group__track_id=track.id,
                    left_at__isnull=True,
                ).values("user_id")
            )
        ).values_list("id", flat=True)
    )

    if not affected_user_ids:
        return

    terminated_count = 0
    skipped_admin_count = 0
    for user in User.objects.filter(id__in=affected_user_ids).iterator():
        if is_operational_admin(user):
            skipped_admin_count += 1
            continue
        terminate_user_sessions(user)
        terminated_count += 1

    logger.info(
        "track.archive.sessions_terminated",
        extra={
            "track_id": track.id,
            "terminated_user_count": terminated_count,
            "skipped_admin_count": skipped_admin_count,
        },
    )


@transaction.atomic
def restore_track(track_id: int, requesting_user=None) -> Dict[str, Any]:
    if not _is_global_admin(requesting_user):
        return {"msg": "Only global admins can restore tracks", "data": None}

    try:
        track = Tracks.objects.get(id=track_id)
    except Tracks.DoesNotExist:
        return {"msg": "Track not found", "data": None}

    track.is_archived = False
    track.save(update_fields=["is_archived"])
    return {"msg": "Track restored successfully", "data": _serialize(track)}


def list_states() -> Dict[str, Any]:
    """List all country/state combinations for the track creation dropdown."""
    states = list(
        CountryStates.objects.select_related("country")
        .order_by("country__country_name", "state_name")
        .values("id", "state_name", "country__country_name")
    )
    return {
        "msg": "States retrieved successfully",
        "data": [
            {
                "id": s["id"],
                "stateName": s["state_name"],
                "countryName": s["country__country_name"],
            }
            for s in states
        ],
    }
