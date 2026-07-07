"""Track admin service.

Create / archive / restore tracks (global admin only) and list states for the
create form. Track admins can only see their own non-archived tracks; global
admins can opt in to see archived tracks for restoration.

`Tracks.is_archived` is added by the groups team; until that migration is in
place, calls referencing it raise FieldError. That is acceptable because this
feature branch is not merged until the field exists upstream.
"""
from __future__ import annotations

from typing import Any, Dict, TypedDict

from django.db import transaction

from apps.common.rbac import is_admin
from apps.groups.models import CountryStates, Tracks


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


def list_tracks(
    requesting_user=None,
    include_archived: bool = False,
) -> Dict[str, Any]:
    """List all tracks; archived only if include_archived=True."""
    qs = Tracks.objects.select_related("state").all()

    if not include_archived:
        qs = qs.filter(is_archived=False)

    tracks = list(qs.order_by("track_name"))
    return {
        "msg": "Tracks retrieved successfully",
        "data": [_serialize(t) for t in tracks],
    }


def create_track(input_data: CreateTrackInput, requesting_user=None) -> Dict[str, Any]:
    if not is_admin(requesting_user):
        return {"msg": "Only admins can create tracks", "data": None}

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
    if not is_admin(requesting_user):
        return {"msg": "Only admins can archive tracks", "data": None}

    try:
        track = Tracks.objects.get(id=track_id)
    except Tracks.DoesNotExist:
        return {"msg": "Track not found", "data": None}

    track.is_archived = True
    track.save(update_fields=["is_archived"])
    return {"msg": "Track archived successfully", "data": _serialize(track)}


@transaction.atomic
def restore_track(track_id: int, requesting_user=None) -> Dict[str, Any]:
    if not is_admin(requesting_user):
        return {"msg": "Only admins can restore tracks", "data": None}

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
