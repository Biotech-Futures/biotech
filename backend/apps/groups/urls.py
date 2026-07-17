from rest_framework.routers import DefaultRouter
from .views import CountryViewSet, GroupMemberViewSet, GroupViewSet

router = DefaultRouter()
router.register(r'countries', CountryViewSet, basename="countries")
router.register(r'group-members', GroupMemberViewSet, basename='group-members')
router.register(r'groups', GroupViewSet, basename="groups")
urlpatterns = router.urls