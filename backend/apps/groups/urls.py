from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CountryViewSet, GroupMemberViewSet, TrackViewSet, GroupViewSet

router = DefaultRouter()
router.register(r'countries', CountryViewSet, basename="countries")
router.register(r'group-members', GroupMemberViewSet, basename='group-members')
router.register(r'tracks', TrackViewSet, basename='tracks')
router.register(r'groups', GroupViewSet, basename="groups")
urlpatterns = router.urls