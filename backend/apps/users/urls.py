from django.urls import path
from . import views
from .views import UsersRetrieveView, UserListHTMLView, UsersRetrieveUpdateView, MeRetrieveView, UserRegisterView, ReceiveJoinPermissionView, UnallocatedStudentsListView, UnallocatedMentorsListView, UnallocatedSummaryView

urlpatterns = [
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("users/me", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('registration', UserRegisterView.as_view(), name = "registration"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("groups/unallocated/students/", UnallocatedStudentsListView.as_view(), name="unallocated-students"),
    path("groups/unallocated/mentors/", UnallocatedMentorsListView.as_view(), name="unallocated-mentors"),
    path("groups/unallocated/summary/", UnallocatedSummaryView.as_view(), name="unallocated-summary"),
]