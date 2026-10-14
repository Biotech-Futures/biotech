from django.urls import path
from .views import (
    UserListHTMLView,
    UsersRetrieveUpdateView,
    MeRetrieveView,
    ReceiveJoinPermissionView,
    AdminOperationalSummaryView,
    BulkUserStatusView,
    PasswordLoginView,
    SetPasswordView,
)
from .registration_intake import RegistrationIntakeView, RegistrationManagementView

urlpatterns = [
    path("login/", PasswordLoginView.as_view(), name="password-login"),
    path("set-password/", SetPasswordView.as_view(), name="set-password"),
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("users/me/", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('registration', RegistrationIntakeView.as_view(), name="registration"),
    path('registration/', RegistrationIntakeView.as_view(), name="registration-slash"),
    path("registration-intake/", RegistrationIntakeView.as_view(), name="registration-intake"),
    path("registration-management/", RegistrationManagementView.as_view(), name="registration-management"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("admin/summary/", AdminOperationalSummaryView.as_view(), name="admin-summary"),
    path("admin/users/bulk-status/", BulkUserStatusView.as_view(), name="admin-bulk-user-status"),
]
