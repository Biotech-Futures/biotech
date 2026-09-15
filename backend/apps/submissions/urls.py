from django.urls import path

from .views import (
    GroupSubmissionFileDownloadView,
    GroupSubmissionFilePreviewView,
    GroupSubmissionFileView,
    GroupSubmissionReopenView,
    GroupSubmissionSubmitView,
    GroupSubmissionView,
    SendSubmissionRemindersView,
)

# Mounted at /api/v1/submissions/ only. No legacy unprefixed alias: nothing
# predates this feature, so there are no existing clients to keep working.
urlpatterns = [
    # Called by a scheduler, not a person: it authenticates with a shared
    # secret rather than a session.
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
    # ``slot`` is one of poster / report / prototype; the view 404s anything else.
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
    # Poster and report only — see GroupSubmissionFilePreviewView for why the
    # prototype slot is deliberately excluded.
    path(
        "groups/<int:group_id>/files/<str:slot>/preview/",
        GroupSubmissionFilePreviewView.as_view(),
        name="group-submission-file-preview",
    ),
]
