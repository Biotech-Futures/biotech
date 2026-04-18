from django.urls import path
from .views import AnnouncementCreateView, AnnouncementListView, AnnouncementDeleteView

urlpatterns = [
    path('v1/', AnnouncementListView.as_view(), name='announcement-list'),
    path('v1/create/', AnnouncementCreateView.as_view(), name='announcement-create'),
    path('v1/<int:pk>/delete/', AnnouncementDeleteView.as_view(), name='announcement-delete'),
]
