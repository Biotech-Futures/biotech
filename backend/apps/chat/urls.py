from django.urls import path
from rest_framework_nested import routers
from .views import MessageViewSet, MessageDestroyView

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)

urlpatterns = router.urls + [
    # Flat delete route — only message_id is needed; group_id is read from
    # the message instance itself.
    path(
        "messages/<int:pk>/",
        MessageDestroyView.as_view(),
        name="message-destroy",
    ),
]
