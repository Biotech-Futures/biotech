from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import (
    EventViewSet,
    EventInviteCreateView,
    EventInviteListHTMLView,
    EventInviteListMeHTMLView,
    MarkAttendanceView
)

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    # router provides:
    #   GET    /events/v1/              -> list
    #   POST   /events/v1/              -> create
    #   GET    /events/v1/{id}/         -> retrieve
    #   PATCH  /events/v1/{id}/         -> update
    #   DELETE /events/v1/{id}/         -> delete (soft)
    #   POST   /events/v1/{id}/register/ -> register for event
    #   POST   /events/v1/{id}/cancel/  -> cancel registration
    #   GET    /events/v1/{id}/my-registration/ -> check registration status
    #   GET    /events/v1/{id}/attendees/ -> view attendees (admin/host only)
    path("", include(router.urls)),

    # Event invite endpoints
    path('api/v1/events/<int:id>/invite/<int:uid>', EventInviteCreateView.as_view(), name="create-eventinv"),
    path('api/v1/events/<int:id>/invites', EventInviteListHTMLView.as_view(), name="list-eventinv"),
    path('api/v1/events/invites/me', EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),

    # Mark attendance endpoint
    path('v1/invites/<int:invite_id>/mark-attendance/', MarkAttendanceView.as_view(), name="mark-attendance"),
]
