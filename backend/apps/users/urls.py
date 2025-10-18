from django.urls import path
from . import views
from .views import UsersRetrieveView, UserListHTMLView, UsersRetrieveUpdateView, MeRetrieveView, UserRegisterView, ReceiveJoinPermissionView

urlpatterns = [
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("users/me/", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('registration', UserRegisterView.as_view(), name = "registration"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm")
]