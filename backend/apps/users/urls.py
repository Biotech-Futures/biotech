from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users import views

urlpatterns = [
    path("auth/send-code/", views.SendLoginCodeView.as_view(), name="send_login_code"),
    path("auth/login/", views.VerifyLoginCodeView.as_view(), name="verify_login_code"),
    path("auth/magic/", views.magic_login, name="magic_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]