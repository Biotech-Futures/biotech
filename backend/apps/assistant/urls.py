from django.urls import path

from .views import AssistantAskView

# Mounted at /api/v1/assistant/ from config.urls.
urlpatterns = [
    path("ask/", AssistantAskView.as_view(), name="assistant-ask"),
]
