from django.urls import path

from .views import (
    AllSubmissionsDownloadView,
    BulkUploadMarksView,
    ComponentDownloadView,
    ComponentMarkingListView,
    FinalistCandidatesView,
    FinalistListView,
    FinalistToggleView,
    GradeBulkView,
    GradeUpdateView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupCategoriesView,
    GroupDownloadView,
    GroupMarkingView,
    GroupResultsCertificateView,
    GroupResultsSummaryView,
    GroupResultsView,
)

app_name = "grading"

urlpatterns = [
    # Per-group marking payload (composite: submissions + rubric + grades).
    path("groups/<int:group_id>/", GroupMarkingView.as_view(), name="group-marking"),
    # The Results section on the group's own page, for its members and admins.
    path("groups/<int:group_id>/results/", GroupResultsView.as_view(), name="group-results"),
    path(
        "groups/<int:group_id>/results/summary/",
        GroupResultsSummaryView.as_view(),
        name="group-results-summary",
    ),
    path(
        "groups/<int:group_id>/results/certificate/<int:user_id>/",
        GroupResultsCertificateView.as_view(),
        name="group-results-certificate",
    ),
    # Sync zip of one group's submissions (bounded — up to 4 components).
    path("groups/<int:group_id>/download/", GroupDownloadView.as_view(), name="group-download"),
    # The marking key's header categories (product / solution) for one group.
    path("groups/<int:group_id>/categories/", GroupCategoriesView.as_view(), name="group-categories"),
    # Per-component table — every group's status for one component.
    path("components/<str:code>/", ComponentMarkingListView.as_view(), name="component-list"),
    # Async bulk export for a single component — returns 202 + job id.
    path("components/<str:code>/download/", ComponentDownloadView.as_view(), name="component-download"),
    # Async export of everything — every group, every component.
    path("download-all/", AllSubmissionsDownloadView.as_view(), name="download-all"),
    # Bulk mark upload (xlsx/csv). dry_run=true previews the diff.
    path("components/<str:code>/bulk-upload/", BulkUploadMarksView.as_view(), name="component-bulk-upload"),
    # Job polling endpoint for the async download dialog.
    path("jobs/<int:pk>/", GradingJobDetailView.as_view(), name="job-detail"),
    # Stream the finished artefact back through Django (avoids exposing the
    # storage backend's URL scheme to the browser).
    path("jobs/<int:pk>/download/", GradingJobDownloadView.as_view(), name="job-download"),
    # Bulk upsert of grades — used by the per-group marking form's Save button.
    path("grades/bulk/", GradeBulkView.as_view(), name="grade-bulk"),
    # PATCH a single grade — used by inline edits and quick amendments.
    path("grades/<int:pk>/", GradeUpdateView.as_view(), name="grade-detail"),

    # M8 — finalist flagging (the finalist email is Management's).
    path("finalists/", FinalistListView.as_view(), name="finalist-list"),
    path("finalists/candidates/", FinalistCandidatesView.as_view(), name="finalist-candidates"),
    path("groups/<int:group_id>/finalist/", FinalistToggleView.as_view(), name="finalist-toggle"),
]
