from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    EventInviteCreateView,
    EventInviteListHTMLView,
    EventInviteListMeHTMLView,
    EventRsvpSetView,
    EventSelfRegisterView,
    EventViewSet,
)

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
    # Authenticated self-registration (shortcut: "set my RSVP to GOING").
    # Kept as a stable URL so the FE's existing Register button doesn't
    # churn while we add Maybe / Decline via the more general /rsvp/.
    path("v1/<int:id>/register/", EventSelfRegisterView.as_view(), name="event-self-register"),

    # Full user-side RSVP control. Accepts
    # ``{"rsvp_status": "going" | "maybe" | "declined"}``. Same gate
    # and idempotency as /register/. Note: distinct from the admin
    # invite endpoint below (``/rsvp/<int:uid>``) — that path has an
    # additional uid segment so the two do not collide.
    path("v1/<int:id>/rsvp/", EventRsvpSetView.as_view(), name="event-self-rsvp"),
    path("v1/<int:id>/rsvp/<int:uid>", EventInviteCreateView.as_view(), name="create-event-rsvp"),
    path("v1/<int:id>/rsvps", EventInviteListHTMLView.as_view(), name="list-event-rsvp"),
    path("v1/rsvps/me", EventInviteListMeHTMLView.as_view(), name="list-event-rsvp-me"),
    path("v1/<int:id>/invite/<int:uid>", EventInviteCreateView.as_view(), name="create-eventinv"),
    path("v1/<int:id>/invites", EventInviteListHTMLView.as_view(), name="list-eventinv"),
    path("v1/invites/me", EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),
]
