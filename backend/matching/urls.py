from django.urls import path
from django.http import JsonResponse
from .views import (
    health, auto_group, auto_group_fallback, assign_mentors, reset_groups,
    replace_group_mentor, deactivate_mentor,
    bulk_inactive_mentors_preview, bulk_replace_inactive_mentors,
)

def health(_):
    return JsonResponse({"status": "ok", "service": "ws3-backend"})

urlpatterns = [
    path("health/", health),
    path("auto_group/", auto_group),
    path("auto_group_fallback/", auto_group_fallback),
    path("assign_mentors/", assign_mentors),
    path("reset_groups/", reset_groups),
    # mentor replacement & bulk
    path("replace_group_mentor/", replace_group_mentor),
    path("deactivate_mentor/", deactivate_mentor),
    path("bulk_inactive_mentors_preview/", bulk_inactive_mentors_preview),
    path("bulk_replace_inactive_mentors/", bulk_replace_inactive_mentors),
]

