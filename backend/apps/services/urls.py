from django.urls import path   
from . import views

urlpatterns = [
    path('csrf/', views.csrf_token_view, name='csrf_token'),
    path('send-login-code/', views.SendLoginCodeView.as_view(), name='send_login_code'),
    path('verify-login-code/', views.VerifyLoginCodeView.as_view(), name='verify_login_code'),
    path('magic/', views.MagicLoginView.as_view(), name='magic_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('password-reset/request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('test-email/', views.test_email_template, name='test_email_template'),
    path('test-email-preview/', views.test_email_preview, name='test_email_preview'),
]