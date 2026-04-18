from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import EventViewSet, EventInviteCreateView, EventInviteListHTMLView, EventInviteListMeHTMLView

router = SimpleRouter()
router.register(r"v1", EventViewSet, basename="events")

urlpatterns = [
    # router provides:
    #   GET  /events/v1/   -> list
    #   POST /events/v1/   -> create
    path("", include(router.urls)),
    path('v1/<int:id>/invite/<int:uid>', EventInviteCreateView.as_view(), name="create-eventinv"),
    path('v1/<int:id>/invites', EventInviteListHTMLView.as_view(), name="list-eventinv"),
    path('v1/invites/me', EventInviteListMeHTMLView.as_view(), name="list-eventinv-me"),
]
