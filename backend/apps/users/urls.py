from django.urls import path
from . import views
from .views import UsersRetrieveView

urlpatterns = [
    path("api/v1/users/<int:pk>/", UsersRetrieveView.as_view(), name="user-detail"),
]