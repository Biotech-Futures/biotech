from django.urls import path
from . import views
from .views import UsersRetrieveView, UserListHTMLView, UsersRetrieveUpdateView, MeRetrieveView, UserRegisterView

urlpatterns = [
    path("api/v1/users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("api/v1/users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("api/v1/users/me", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path('api/v1/registration', UserRegisterView.as_view(), name = "registration")
]