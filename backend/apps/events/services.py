"""Business logic for the events app.

Keeping query and registration mechanics here (rather than inside views)
maintains the project's "no fat views" rule: ``views.py`` should only
parse the request, enforce permissions, and shape the response.
"""

from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .models import EventRsvp, Events


def get_user_registered_event_ids(user):
    """Return a ``set`` of event ids ``user`` has *registered* for.

    "Registered" is defined narrowly as ``rsvp_status == GOING`` — the
    user has actively committed to attending. PENDING / MAYBE / DECLINED
    all serialize as ``registered: false``. This is the single source
    of truth used by both the per-row ``EventSerializer.registered``
    field and the ``?registered=true`` / ``?mine=true`` filters, so any
    future contract change happens in exactly one place.

    The 4-value ``RsvpStatus`` enum stays the canonical record of
    *intent*; ``registered`` is a derived projection of "going".

    Returning a ``set`` keeps O(1) membership checks for the serializer
    so listing N events stays O(N) without an N+1 query against
    ``EventRsvp``.
    """
    if not user or not user.is_authenticated:
        return set()
    return set(
        EventRsvp.objects.filter(
            user=user,
            rsvp_status=EventRsvp.RsvpStatus.GOING,
        ).values_list("event_id", flat=True)
    )


def register_user_for_event(user, event_id):
    """Register ``user`` for the event with primary key ``event_id``.

    Returns ``(event, rsvp, created)``:
      - ``event``  : the resolved ``Events`` instance.
      - ``rsvp``   : the persisted ``EventRsvp`` row for this user/event.
      - ``created``: ``True`` if a new RSVP row was created on this call;
                     ``False`` if the user was already registered (the
                     existing row is returned untouched, idempotent).

    Raises:
      - ``rest_framework.exceptions.NotFound`` if the event is missing
        or soft-deleted.
      - ``rest_framework.exceptions.ValidationError`` if the event has
        already ended (registration is closed).

    Idempotent by design: a second call by the same user for the same
    event returns ``created=False`` rather than erroring, satisfying
    the spec's "prevent duplicate registrations" guidance without
    surfacing a confusing 409 to the FE.

    Uses ``update_or_create`` (not ``get_or_create``) so a user who
    previously RSVP'd ``DECLINED`` / ``PENDING`` / ``MAYBE`` and then
    hits ``/register/`` is *promoted* to ``GOING``. Returning the
    spec's ``{"registered": true}`` while leaving the underlying RSVP
    in a non-going state would be a lie, and the FE has no other path
    to flip a declined RSVP back to going from this endpoint.
    """
    event = (
        Events.objects.filter(id=event_id, deleted_at__isnull=True).first()
    )
    if event is None:
        raise NotFound("Event not found.")

    if event.ends_datetime < timezone.now():
        raise ValidationError("Event has already ended; registration is closed.")

    rsvp, created = EventRsvp.objects.update_or_create(
        event=event,
        user=user,
        defaults={
            "rsvp_status": EventRsvp.RsvpStatus.GOING,
            "responded_at": timezone.now(),
        },
    )
    return event, rsvp, created
