from django.urls import path
from . import views
from .views import UsersRetrieveView, UserListHTMLView, UsersRetrieveUpdateView, UnifiedRegisterView

urlpatterns = [
    path("api/v1/users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("api/v1/users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("api/v1/auth/register", UnifiedRegisterView.as_view(), name="user-register"),
]