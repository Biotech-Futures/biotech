from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, RoleAssignmentHistoryViewSet

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"role-assignments", RoleAssignmentHistoryViewSet, basename="role-assignments")



urlpatterns = router.urls