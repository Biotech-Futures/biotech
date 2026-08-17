from django.urls import path

from .views import (
    ComponentMarkingListView,
    GradeBulkView,
    GradeUpdateView,
    GroupMarkingView,
)

app_name = "grading"

urlpatterns = [
    # Per-group marking payload (composite: submissions + rubric + grades).
    path("groups/<int:group_id>/", GroupMarkingView.as_view(), name="group-marking"),
    # Per-component table — every group's status for one component.
    path("components/<str:code>/", ComponentMarkingListView.as_view(), name="component-list"),
    # Bulk upsert of grades — used by the per-group marking form's Save button.
    path("grades/bulk/", GradeBulkView.as_view(), name="grade-bulk"),
    # PATCH a single grade — used by inline edits and quick amendments.
    path("grades/<int:pk>/", GradeUpdateView.as_view(), name="grade-detail"),
]
