from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    EventBulkInviteView,
    EventInviteCreateView,
    EventInviteListHTMLView,
    EventInviteListMeHTMLView,
    EventRsvpSetView,
    EventViewSet,
    RsvpReminderTriggerView,
)

router = SimpleRouter()
# Canonical route at the app root — exposed as ``/events/...`` (legacy mount)
# and ``/api/v1/events/...`` (canonical) by config.urls.
router.register(r"", EventViewSet, basename="events")

# Canonical app-root patterns. Specific paths come BEFORE ``*router.urls`` so
# the router's catch-all ``<pk>/`` detail pattern doesn't shadow them.
_canonical = [
    # ``/rsvps/me/`` — current-user RSVP list (full user-side control:
    # accepted/tentative/declined). Distinct from the admin invite path
    # ``/<id>/rsvp/<uid>/`` which targets another user.
    path("rsvps/me/", EventInviteListMeHTMLView.as_view(), name="list-event-rsvp-me"),
    path("<int:id>/rsvp/", EventRsvpSetView.as_view(), name="event-self-rsvp"),
    path("<int:id>/rsvp/bulk/", EventBulkInviteView.as_view(), name="event-bulk-invite"),
    path("<int:id>/rsvp/<int:uid>/", EventInviteCreateView.as_view(), name="create-event-rsvp"),
    path("<int:id>/rsvps/", EventInviteListHTMLView.as_view(), name="list-event-rsvp"),
    # Cron-trigger for the 24h RSVP reminder dispatcher. Hit hourly by
    # .github/workflows/rsvp-reminders.yml with a shared-secret header.
    # Listed under the canonical root so it's also reachable at
    # ``/api/v1/events/admin/send-rsvp-reminders/`` — the legacy
    # ``/events/v1/admin/send-rsvp-reminders/`` keeps resolving via the
    # ``v1/`` alias below so the existing workflow doesn't need changes.
    path(
        "admin/send-rsvp-reminders/",
        RsvpReminderTriggerView.as_view(),
        name="rsvp-reminder-trigger",
    ),
    path("", include(router.urls)),
]

urlpatterns = [
    # Legacy ``/events/v1/...`` alias — preserves the original paths so any
    # client that hasn't migrated keeps resolving. Listed FIRST so the canonical
    # patterns below are the last named registration and win ``reverse()``
    # lookups. Drop once all consumers move off the ``v1/`` segment.
    path("v1/", include(_canonical)),
    *_canonical,
]
