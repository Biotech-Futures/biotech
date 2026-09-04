from django.urls import path

from .views import (
    BulkUploadMarksView,
    CertificatesReleaseView,
    GroupExtensionDetailView,
    GroupExtensionListView,
    SubmissionDeadlineView,
    ComponentAnalyticsView,
    ComponentDownloadView,
    ComponentMarkingListView,
    FinalistCandidatesView,
    FinalistListView,
    FinalistNotifyAllView,
    FinalistToggleView,
    GradeBulkView,
    GradeUpdateView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GradingSettingsView,
    GroupDownloadView,
    GroupMarkingView,
    MarksReleaseView,
    MyCertificateView,
    MyGradesView,
    MySummaryView,
    SupervisorDownloadView,
    SupervisorGradesView,
)

app_name = "grading"

urlpatterns = [
    # Per-group marking payload (composite: submissions + rubric + grades).
    path("groups/<int:group_id>/", GroupMarkingView.as_view(), name="group-marking"),
    # Sync zip of one group's submissions (bounded — up to 4 components).
    path("groups/<int:group_id>/download/", GroupDownloadView.as_view(), name="group-download"),
    # Per-component table — every group's status for one component.
    path("components/<str:code>/", ComponentMarkingListView.as_view(), name="component-list"),
    # Async bulk export for a single component — returns 202 + job id.
    path("components/<str:code>/download/", ComponentDownloadView.as_view(), name="component-download"),
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

    # Submission deadline: view + set the window students can submit in.
    path("deadline/", SubmissionDeadlineView.as_view(), name="deadline"),
    # Per-team extensions on top of the global deadline.
    path("deadline/extensions/", GroupExtensionListView.as_view(), name="deadline-extensions"),
    path("deadline/extensions/<int:group_id>/", GroupExtensionDetailView.as_view(), name="deadline-extension-detail"),

    # M6 — release toggles + configurable director/template settings.
    path("release/", MarksReleaseView.as_view(), name="release"),
    path("certificates-release/", CertificatesReleaseView.as_view(), name="certificates-release"),
    path("settings/", GradingSettingsView.as_view(), name="settings"),

    # Student-facing read views (gated on MarksRelease.released_at).
    path("me/grades/", MyGradesView.as_view(), name="me-grades"),
    path("me/summary/", MySummaryView.as_view(), name="me-summary"),
    path("me/certificate/", MyCertificateView.as_view(), name="me-certificate"),

    # Supervisor-facing (gated on release + student.supervisor FK).
    path("supervisor/students/grades/", SupervisorGradesView.as_view(), name="supervisor-grades"),
    path("supervisor/download/", SupervisorDownloadView.as_view(), name="supervisor-download"),

    # M8 — finalist flagging + optional notification.
    path("finalists/", FinalistListView.as_view(), name="finalist-list"),
    path("finalists/notify/", FinalistNotifyAllView.as_view(), name="finalist-notify"),
    path("finalists/candidates/", FinalistCandidatesView.as_view(), name="finalist-candidates"),
    path("groups/<int:group_id>/finalist/", FinalistToggleView.as_view(), name="finalist-toggle"),

    # M9 — read-only analytics for Team 4's dashboards.
    path("components/<str:code>/analytics/", ComponentAnalyticsView.as_view(), name="component-analytics"),
]
