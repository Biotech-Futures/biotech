from rest_framework_nested import routers
from .views import GifViewSet, MentionViewSet, MessageViewSet

router = routers.SimpleRouter()
router.register(
    r"groups/(?P<group_pk>\d+)/messages",
    MessageViewSet,
    basename="group-messages",
)
router.register(r"mentions", MentionViewSet, basename="mentions")

# GIF endpoints are not group-scoped and the FE builds URLs without a
# trailing slash (``/gifs/search?q=...``). A dedicated router with
# ``trailing_slash=False`` keeps the URL stable and avoids the
# ``APPEND_SLASH`` 301 that would otherwise convert the GET to a redirect
# (a non-issue for GET but a footgun if we ever add POST endpoints here).
gif_router = routers.SimpleRouter(trailing_slash=False)
gif_router.register(r"gifs", GifViewSet, basename="gifs")

urlpatterns = router.urls + gif_router.urls
