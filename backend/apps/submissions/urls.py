from django.urls import path

from .views import (
    GroupSubmissionFileDownloadView,
    GroupSubmissionFileView,
    GroupSubmissionSubmitView,
    GroupSubmissionView,
)

# Mounted by config.urls at /api/v1/submissions/ only. Unlike the older apps
# there is no legacy unprefixed alias: nothing predates this feature, so there
# are no existing clients to keep working.
urlpatterns = [
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
]
