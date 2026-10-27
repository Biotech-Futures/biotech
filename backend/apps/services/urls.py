from django.urls import path
from . import views

urlpatterns = [
    path('email/track/open/<uuid:token>.gif', views.track_email_open, name='email_tracking_open'),
    path('email/track/click/<str:payload>/', views.track_email_click, name='email_tracking_click'),
    path('csrf/', views.csrf_token_view, name='csrf_token'),
    path('send-login-code/', views.SendLoginCodeView.as_view(), name='send_login_code'),
    path('verify-login-code/', views.VerifyLoginCodeView.as_view(), name='verify_login_code'),
    path('magic/', views.MagicLoginView.as_view(), name='magic_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('password-reset/request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
