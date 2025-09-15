from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('roles', views.RoleViewSet)

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/role-assignments/', views.assign_role, name='assign-role'),
]
