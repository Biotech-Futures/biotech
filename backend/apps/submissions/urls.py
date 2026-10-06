from django.urls import path

from .finalist_views import (
    FinalistEntryView,
    FinalistPresentationDownloadView,
    FinalistPresentationPreviewView,
    FinalistPresentationView,
    FinalistReopenView,
    FinalistSubmitView,
)
from .views import (
    GroupSubmissionFileDownloadView,
    GroupSubmissionFilePreviewView,
    GroupSubmissionFileView,
    GroupSubmissionReopenView,
    GroupSubmissionSubmitView,
    GroupSubmissionView,
    SendSubmissionRemindersView,
)

# Mounted at /api/v1/submissions/.
urlpatterns = [
    # Called by a scheduler with a shared token rather than a session.
    path(
        "admin/send-reminders/",
        SendSubmissionRemindersView.as_view(),
        name="submission-send-reminders",
    ),
    path(
        "groups/<int:group_id>/",
        GroupSubmissionView.as_view(),
        name="group-submission",
    ),
    path(
        "groups/<int:group_id>/submit/",
        GroupSubmissionSubmitView.as_view(),
        name="group-submission-submit",
    ),
    path(
        "groups/<int:group_id>/reopen/",
        GroupSubmissionReopenView.as_view(),
        name="group-submission-reopen",
    ),
    # slot is poster, report or prototype.
    path(
        "groups/<int:group_id>/files/<str:slot>/",
        GroupSubmissionFileView.as_view(),
        name="group-submission-file",
    ),
    path(
        "groups/<int:group_id>/files/<str:slot>/download/",
        GroupSubmissionFileDownloadView.as_view(),
        name="group-submission-file-download",
    ),
    # Poster and report only.
    path(
        "groups/<int:group_id>/files/<str:slot>/preview/",
        GroupSubmissionFilePreviewView.as_view(),
        name="group-submission-file-preview",
    ),
    path(
        "finalist/groups/<int:group_id>/",
        FinalistEntryView.as_view(),
        name="finalist-entry",
    ),
    path(
        "finalist/groups/<int:group_id>/presentation/",
        FinalistPresentationView.as_view(),
        name="finalist-presentation",
    ),
    path(
        "finalist/groups/<int:group_id>/presentation/download/",
        FinalistPresentationDownloadView.as_view(),
        name="finalist-presentation-download",
    ),
    path(
        "finalist/groups/<int:group_id>/presentation/preview/",
        FinalistPresentationPreviewView.as_view(),
        name="finalist-presentation-preview",
    ),
    path(
        "finalist/groups/<int:group_id>/submit/",
        FinalistSubmitView.as_view(),
        name="finalist-submit",
    ),
    path(
        "finalist/groups/<int:group_id>/reopen/",
        FinalistReopenView.as_view(),
        name="finalist-reopen",
    ),
]
