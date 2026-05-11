from rest_framework_nested import routers
from .views import MessageViewSet, GifViewSet

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)
router.register(
    r"gifs",
    GifViewSet,
    basename="chat-gifs",
)

urlpatterns = router.urls
