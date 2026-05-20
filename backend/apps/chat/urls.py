from rest_framework_nested import routers
from .views import MentionViewSet, MessageViewSet

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)
router.register(r"mentions", MentionViewSet, basename="mentions")

urlpatterns = router.urls
