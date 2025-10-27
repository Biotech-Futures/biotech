from django.urls import path
from .views import (
	SubscribeView,
	UnsubscribeView,
	ResubscribeView,
	SubscribersListView,
)

urlpatterns = [
	path("subscribe", SubscribeView.as_view(), name="newsletter-subscribe"),
	path("unsubscribe", UnsubscribeView.as_view(), name="newsletter-unsubscribe"),
	path("resubscribe", ResubscribeView.as_view(), name="newsletter-resubscribe"),
	path("subscribers", SubscribersListView.as_view(), name="newsletter-subscribers"),
]