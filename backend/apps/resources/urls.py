from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, RoleAssignmentHistoryViewSet, ResourcesViewSet

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"role-assignments", RoleAssignmentHistoryViewSet, basename="role-assignments")
router.register(r"resource-files", ResourcesViewSet, basename="resource-files")

urlpatterns = router.urls