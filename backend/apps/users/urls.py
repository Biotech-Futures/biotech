from django.urls import path
from . import views
from .views import UsersRetrieveView, UserListHTMLView, UsersRetrieveUpdateView, MeRetrieveView, UserRegisterView, ReceiveJoinPermissionView, UnallocatedStudentsListView, UnallocatedMentorsListView, UnallocatedSummaryView

urlpatterns = [
    path("api/v1/users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("api/v1/users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("api/v1/users/me", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('api/v1/registration', UserRegisterView.as_view(), name = "registration"),
    path('api/v1/updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("api/v1/groups/unallocated/students/", UnallocatedStudentsListView.as_view(), name="unallocated-students"),
    path("api/v1/groups/unallocated/mentors/", UnallocatedMentorsListView.as_view(), name="unallocated-mentors"),
    path("api/v1/groups/unallocated/summary/", UnallocatedSummaryView.as_view(), name="unallocated-summary"),
]