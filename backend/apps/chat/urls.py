from rest_framework_nested import routers
from .views import MessageViewSet

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)

urlpatterns = router.urls
