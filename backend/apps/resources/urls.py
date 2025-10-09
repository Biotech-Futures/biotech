from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, RoleAssignmentHistoryViewSet, ResourcesViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"role-assignments", RoleAssignmentHistoryViewSet, basename="role-assignments")
router.register(r"resource-files", ResourcesViewSet, basename="resource-files")

# API v1 router for versioned endpoints
v1_router = DefaultRouter()
v1_router.register(r"roles", RoleViewSet, basename="v1-roles")

urlpatterns = [
    # API v1 versioned endpoints
    path('api/v1/', include(v1_router.urls)),
    # Original endpoints for backward compatibility
] + router.urls
