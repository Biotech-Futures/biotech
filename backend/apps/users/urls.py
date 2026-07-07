from django.urls import path
from . import views
from .views import (
    UserListHTMLView,
    UsersRetrieveUpdateView,
    MeRetrieveView,
    UserRegisterView,
    ReceiveJoinPermissionView,
    AdminOperationalSummaryView,
    BulkUserStatusView,
    PasswordLoginView,
)

urlpatterns = [
    path("login/", PasswordLoginView.as_view(), name="password-login"),
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("users/me/", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('registration', UserRegisterView.as_view(), name = "registration"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("admin/summary/", AdminOperationalSummaryView.as_view(), name="admin-summary"),
    path("admin/users/bulk-status/", BulkUserStatusView.as_view(), name="admin-bulk-user-status"),
]
