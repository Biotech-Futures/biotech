from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CountryViewSet, GroupMemberViewSet

router = DefaultRouter()
router.register(r'countries', CountryViewSet, basename="countries")
router.register(r'group-members', GroupMemberViewSet, basename='group-members')
urlpatterns = router.urls