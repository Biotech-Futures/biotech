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
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
    # /rsvp/ — full user-side control (accepted/tentative/declined).
    # Distinct from the admin invite path (/rsvp/<uid>/) by the trailing uid.
    path("v1/<int:id>/rsvp/", EventRsvpSetView.as_view(), name="event-self-rsvp"),
    path("v1/<int:id>/rsvp/bulk/", EventBulkInviteView.as_view(), name="event-bulk-invite"),
    path("v1/<int:id>/rsvp/<int:uid>/", EventInviteCreateView.as_view(), name="create-event-rsvp"),
    path("v1/<int:id>/rsvps/", EventInviteListHTMLView.as_view(), name="list-event-rsvp"),
    path("v1/rsvps/me/", EventInviteListMeHTMLView.as_view(), name="list-event-rsvp-me"),
    # Cron-trigger for the 24h RSVP reminder dispatcher. Hit hourly by
    # .github/workflows/rsvp-reminders.yml with a shared-secret header.
    path(
        "v1/admin/send-rsvp-reminders/",
        RsvpReminderTriggerView.as_view(),
        name="rsvp-reminder-trigger",
    ),
]