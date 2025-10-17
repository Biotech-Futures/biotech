from django.urls import path   
from . import views

urlpatterns = [
    path('send-login-code/', views.SendLoginCodeView.as_view(), name='send_login_code'),
    path('verify-login-code/', views.VerifyLoginCodeView.as_view(), name='verify_login_code'),
    path('magic/', views.magic_login, name='magic_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('test-email/', views.test_email_template, name='test_email_template'),
    path('test-email-preview/', views.test_email_preview, name='test_email_preview'),
]