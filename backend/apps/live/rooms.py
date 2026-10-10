"""The kinds of live room, and who may join a room of each kind."""
from importlib import import_module

# Each kind names a function taking (user, room_id) that says whether the user may join.
ROOM_ACCESS = {
    "submission": "apps.submissions.live:can_join",
}


def can_join(kind: str, user, room_id: int) -> bool:
    path = ROOM_ACCESS.get(kind)
    if path is None:
        return False
    module, name = path.split(":")
    return bool(getattr(import_module(module), name)(user, room_id))


def room_name(kind: str, room_id: int) -> str:
    return f"live.{kind}.{room_id}"


def person(user) -> dict:
    """How someone is named to their teammates in a room."""
    return {"id": user.id, "name": user.first_name or user.get_full_name() or "A teammate"}
