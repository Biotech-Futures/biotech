from django.urls import path
from .supervisor_group_views import (
    SupervisedGroupDetailView,
    SupervisedGroupMembersView,
    SupervisedGroupsView,
    SupervisedInterestCatalogView,
    SupervisedMentorsView,
)
from .views import (
    UserListHTMLView,
    UsersRetrieveUpdateView,
    MeRetrieveView,
    UserRegisterView,
    ReceiveJoinPermissionView,
    AdminOperationalSummaryView,
    BulkUserStatusView,
    PasswordLoginView,
    SetPasswordView,
    SupervisedStudentsView,
)

urlpatterns = [
    path("login/", PasswordLoginView.as_view(), name="password-login"),
    path("set-password/", SetPasswordView.as_view(), name="set-password"),
    path("users/me/", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path("users/supervised-students/", SupervisedStudentsView.as_view(), name="supervised-students"),
    path("users/supervised-groups/mentors/", SupervisedMentorsView.as_view(), name="supervised-mentors"),
    path("users/supervised-groups/interests/", SupervisedInterestCatalogView.as_view(), name="supervised-group-interests"),
    path("users/supervised-groups/", SupervisedGroupsView.as_view(), name="supervised-groups"),
    path("users/supervised-groups/<int:pk>/members/", SupervisedGroupMembersView.as_view(), name="supervised-group-members"),
    path("users/supervised-groups/<int:pk>/", SupervisedGroupDetailView.as_view(), name="supervised-group-detail"),
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path('registration', UserRegisterView.as_view(), name = "registration"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("admin/summary/", AdminOperationalSummaryView.as_view(), name="admin-summary"),
    path("admin/users/bulk-status/", BulkUserStatusView.as_view(), name="admin-bulk-user-status"),
]
