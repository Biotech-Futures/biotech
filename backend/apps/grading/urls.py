from django.urls import path

app_name = "grading"

# Endpoints land here as milestones M2..M9 are implemented. The router is
# mounted in config/urls.py behind ``settings.GRADING_ENABLED`` so the whole
# surface stays 404 in prod until it's ready.
urlpatterns: list[path] = []
