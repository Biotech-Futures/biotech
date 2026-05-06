from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    EventInviteCreateView,
    EventInviteListHTMLView,
    EventInviteListMeHTMLView,
    EventSelfRegisterView,
    EventViewSet,
)

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
    # Authenticated self-registration. Mounted as a dedicated path
    # rather than a viewset @action so the permission boundary
    # ([IsAuthenticated]) lives on a single-purpose view rather than
    # being threaded through the admin-gated viewset.
    path("v1/<int:id>/register/", EventSelfRegisterView.as_view(), name="event-self-register",),
    path("v1/<int:id>/rsvp/<int:uid>", EventInviteCreateView.as_view(), name="create-event-rsvp"),
    path("v1/<int:id>/rsvps", EventInviteListHTMLView.as_view(), name="list-event-rsvp"),
    path("v1/rsvps/me", EventInviteListMeHTMLView.as_view(), name="list-event-rsvp-me"),
    path("v1/<int:id>/invite/<int:uid>", EventInviteCreateView.as_view(), name="create-eventinv"),
    path("v1/<int:id>/invites", EventInviteListHTMLView.as_view(), name="list-eventinv"),
    path("v1/invites/me", EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),
]
