from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import AnnouncementViewSet

router = SimpleRouter()
router.register(r"v1", AnnouncementViewSet, basename="announcements")

urlpatterns = [
    # ========== ROUTER ENDPOINTS (AnnouncementViewSet) ==========
    # Announcement CRUD
    #   GET    /announcements/v1/                   -> list announcements (filtered by role)
    #   POST   /announcements/v1/                   -> create announcement (admin only)
    #   GET    /announcements/v1/{id}/              -> retrieve single announcement
    #   PATCH  /announcements/v1/{id}/              -> update announcement (admin/author only)
    #   DELETE /announcements/v1/{id}/              -> soft delete announcement (admin/author only)
    #
    # Query Parameters:
    #   ?search=keyword                             -> search title, summary, author
    #   ?audience=student                           -> filter by audience (admin only)
    path("", include(router.urls)),
]
