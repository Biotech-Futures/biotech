from django.urls import path
from rest_framework_nested import routers
from .views import MentionViewSet, MessageViewSet, UnreadDigestTriggerView

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)
router.register(r"mentions", MentionViewSet, basename="mentions")

urlpatterns = [
    *router.urls,
    # Cron-only HMAC-guarded trigger for the daily unread-messages digest.
    path(
        "admin/send-unread-digest/",
        UnreadDigestTriggerView.as_view(),
        name="send-unread-digest",
    ),
]
