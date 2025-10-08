from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import RoleViewSet, RoleAssignmentHistoryViewSet

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"role-assignments", RoleAssignmentHistoryViewSet, basename="role-assignments")

# API v1 router for versioned endpoints
v1_router = DefaultRouter()
v1_router.register(r"roles", RoleViewSet, basename="v1-roles")

urlpatterns = [
    # API v1 versioned endpoints
    path('api/v1/', include(v1_router.urls)),
    # Original endpoints for backward compatibility
] + router.urls