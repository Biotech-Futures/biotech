from django.urls import path
from . import views
from .views import (
    AdminUserDetailView,
    AdminUserListView,
    MeRetrieveView,
    UserRegisterView,
    ReceiveJoinPermissionView,
    AdminOperationalSummaryView,
    BulkUserStatusView,
    BulkUserTrackAssignmentView,
    PasswordLoginView,
)

urlpatterns = [
    # Canonical JSON-first login route for API v1 clients.
    path("auth/login/", PasswordLoginView.as_view(), name="password-login"),
    # JSON-first user/admin management surface for SPA and admin integrations.
    path("users/", AdminUserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="user-detail"),
    path("users/me/", MeRetrieveView.as_view(), name="user-me"),
    path('registration', UserRegisterView.as_view(), name = "registration"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("admin/summary/", AdminOperationalSummaryView.as_view(), name="admin-summary"),
    # Explicit admin aliases kept for clarity alongside the shared user-management handlers.
    path("admin/users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/users/bulk-status/", BulkUserStatusView.as_view(), name="admin-bulk-user-status"),
    path("admin/users/bulk-track/", BulkUserTrackAssignmentView.as_view(), name="admin-bulk-user-track"),
]
