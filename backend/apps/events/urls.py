from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import EventInviteCreateView, EventInviteListHTMLView, EventInviteListMeHTMLView, EventMeRsvpView, EventViewSet

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
    # Self-service RSVP is the contract the frontend should use instead of the older admin-style
    # `/rsvp/<uid>` shape that exposed user ids in the path.
    path("v1/<int:id>/rsvps/me/", EventMeRsvpView.as_view(), name="event-rsvp-me"),
    path("v1/<int:id>/rsvp/<int:uid>", EventInviteCreateView.as_view(), name="create-event-rsvp"),
    path("v1/<int:id>/rsvps", EventInviteListHTMLView.as_view(), name="list-event-rsvp"),
    path("v1/rsvps/me", EventInviteListMeHTMLView.as_view(), name="list-event-rsvp-me"),
    path("v1/<int:id>/invite/<int:uid>", EventInviteCreateView.as_view(), name="create-eventinv"),
    path("v1/<int:id>/invites", EventInviteListHTMLView.as_view(), name="list-eventinv"),
    path("v1/invites/me", EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),
]
