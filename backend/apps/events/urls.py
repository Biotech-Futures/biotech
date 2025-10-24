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
    # ========== ROUTER ENDPOINTS (EventViewSet) ==========
    # Event CRUD
    #   GET    /events/v1/                          -> list all upcoming events (public)
    #   POST   /events/v1/                          -> create event (admin only)
    #   GET    /events/v1/{id}/                     -> retrieve single event (public)
    #   PATCH  /events/v1/{id}/                     -> update event (admin/host only)
    #   DELETE /events/v1/{id}/                     -> soft delete event (admin/host only)
    #
    # Event Registration (Custom Actions)
    #   POST   /events/v1/{id}/register/            -> register for event (authenticated)
    #   POST   /events/v1/{id}/cancel/              -> cancel registration (authenticated)
    #   GET    /events/v1/{id}/my-registration/     -> check registration status (authenticated)
    #   GET    /events/v1/{id}/attendees/           -> view event attendees (admin/host only)
    path("", include(router.urls)),

    # ========== LEGACY EVENT INVITE ENDPOINTS ==========
    # Create invite for specific user (admin/mentor only)
    path('api/v1/events/<int:id>/invite/<int:uid>', EventInviteCreateView.as_view(), name="create-eventinv"),

    # List all invites for an event (admin/mentor only)
    path('api/v1/events/<int:id>/invites', EventInviteListHTMLView.as_view(), name="list-eventinv"),

    # List all invites for current user (authenticated)
    path('api/v1/events/invites/me', EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),

    # ========== ATTENDANCE TRACKING ==========
    # Mark attendance for an event invite (admin/host only)
    # PATCH /events/v1/invites/{invite_id}/mark-attendance/
    # Body: {"attendance_status": true}
    path('v1/invites/<int:invite_id>/mark-attendance/', MarkAttendanceView.as_view(), name="mark-attendance"),
]
