"""The kinds of live room, and who may join a room of each kind."""
from importlib import import_module

# Each kind names a function taking (user, room_id) that says whether the user may join.
ROOM_ACCESS = {
    "submission": "apps.submissions.live:can_join",
}


# Kinds whose rooms also share a live-merged document, by the module that keeps it. The module
# provides enabled(), can_edit(user, room_id), state_since(room_id, vector) -> (missing, vector),
# generation(room_id), apply_and_claim(room_id, update, generation, claim_seconds) -> (accepted, claimed),
# save(room_id), flush(room_id), and release_save(room_id), so a room's typists share one save.
ROOM_DOCUMENTS = {
    "submission": "apps.submissions.coedit",
}


def document_for(kind: str):
    path = ROOM_DOCUMENTS.get(kind)
    return import_module(path) if path else None


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
