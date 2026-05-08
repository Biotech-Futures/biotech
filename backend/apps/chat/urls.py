from django.urls import path
from rest_framework_nested import routers

from .views import MessageViewSet, MessageDetailView

# Nested router exposes only the *collection* operations on a group:
#   GET  /chat/groups/<gid>/messages/
#   POST /chat/groups/<gid>/messages/
router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)

# Flat per-message URL serves both verbs from a single view; see
# MessageDetailView for the per-method permission contract. We register two
# names against the same path so existing reverse() calls keep working and
# tests can assert intent (edit vs delete) at the URL layer.
_message_detail = MessageDetailView.as_view()

urlpatterns = router.urls + [
    path("messages/<int:pk>/", _message_detail, name="message-detail"),
    path("messages/<int:pk>/", _message_detail, name="message-update"),
    path("messages/<int:pk>/", _message_detail, name="message-destroy"),
]
