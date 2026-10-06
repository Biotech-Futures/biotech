from django.urls import path

from .views import (
    AnnouncementCategoriesView,
    CertificatesReleaseView,
    FinalistEmailPreviewView,
    FinalistEmailSettingsView,
    FinalistNotifyAllView,
    GradingSettingsView,
    GroupExtensionDetailView,
    GroupExtensionListView,
    GroupResultsCertificateView,
    GroupResultsSummaryView,
    GroupResultsView,
    MarksReleaseView,
    NonFinalistEmailPreviewView,
    NonFinalistEmailSendView,
    NonFinalistEmailView,
    NonSubmissionEmailPreviewView,
    NonSubmissionEmailSendView,
    NonSubmissionEmailView,
    OutcomeAnnouncementPostView,
    OutcomeAnnouncementView,
    PresentationAllocationView,
    PresentationResponsesView,
    PresentationSlidesFileView,
    PresentationSlidesView,
    PresentationSlotDetailView,
    PresentationTimesShownView,
    PresentationSlotListView,
    ResultsEmailPreviewView,
    ResultsEmailSendView,
    ResultsEmailSettingsView,
    ResultsSampleSheetView,
    ResultsSupervisorSheetView,
    SubmissionDeadlineView,
    TemplateDownloadView,
    TemplatePeopleView,
    TemplateScanView,
    TemplateTestRenderView,
    TestEmailView,
)

app_name = "management"

urlpatterns = [
    # Submission deadline: view + set the window students can submit in.
    path("deadline/", SubmissionDeadlineView.as_view(), name="deadline"),
    # Per-team extensions on top of the global deadline.
    path("deadline/extensions/", GroupExtensionListView.as_view(), name="deadline-extensions"),
    path("deadline/extensions/<int:group_id>/", GroupExtensionDetailView.as_view(), name="deadline-extension-detail"),

    # M6 — release toggles + configurable director/template settings.
    path("release/", MarksReleaseView.as_view(), name="release"),
    path("certificates-release/", CertificatesReleaseView.as_view(), name="certificates-release"),
    path("settings/", GradingSettingsView.as_view(), name="settings"),
    # Which placeholders the active template actually contains.
    path(
        "settings/template-scan/<str:kind>/",
        TemplateScanView.as_view(),
        name="settings-template-scan",
    ),
    # The saved template file itself.
    path(
        "settings/template/<str:kind>/",
        TemplateDownloadView.as_view(),
        name="settings-template-download",
    ),
    # Who a template can be tested with, for a real person's document.
    path(
        "settings/test-people/<str:kind>/",
        TemplatePeopleView.as_view(),
        name="settings-test-people",
    ),
    # Render the active template with synthetic data to check placeholders.
    path(
        "settings/test-render/<str:kind>/",
        TemplateTestRenderView.as_view(),
        name="settings-test-render",
    ),

    # Notify Finalists: the finalist email and sending it.
    path("finalists/notify/", FinalistNotifyAllView.as_view(), name="finalist-notify"),
    path("finalists/email/", FinalistEmailSettingsView.as_view(), name="finalist-email"),
    path(
        "finalists/email/preview/",
        FinalistEmailPreviewView.as_view(),
        name="finalist-email-preview",
    ),
    # New Announcement's finalist, non-finalist and non-submission categories.
    path("announcement-categories/", AnnouncementCategoriesView.as_view(), name="announcement-categories"),
    # The in-app announcement that goes with each outcome email: finalist,
    # non-finalist, non-submission, and the results emails.
    path("outcome-announcements/<str:kind>/", OutcomeAnnouncementView.as_view(), name="outcome-announcement"),
    path(
        "outcome-announcements/<str:kind>/post/",
        OutcomeAnnouncementPostView.as_view(),
        name="outcome-announcement-post",
    ),

    # The invitation to teams that submitted but weren't picked, from the
    # Notify Nonfinalist tab.
    path("nonfinalists/", NonFinalistEmailView.as_view(), name="nonfinalist-email"),
    path("nonfinalists/preview/", NonFinalistEmailPreviewView.as_view(), name="nonfinalist-email-preview"),
    path("nonfinalists/send/", NonFinalistEmailSendView.as_view(), name="nonfinalist-email-send"),
    # The same tab's notice to teams that didn't submit.
    path("nonsubmissions/", NonSubmissionEmailView.as_view(), name="nonsubmission-email"),
    path("nonsubmissions/preview/", NonSubmissionEmailPreviewView.as_view(), name="nonsubmission-email-preview"),
    path("nonsubmissions/send/", NonSubmissionEmailSendView.as_view(), name="nonsubmission-email-send"),

    # The Finalist Presentation tab: this year's times finalists can present.
    path(
        "finalists/presentation-slots/",
        PresentationSlotListView.as_view(),
        name="presentation-slots",
    ),
    path(
        "finalists/presentation-slots/<int:slot_id>/",
        PresentationSlotDetailView.as_view(),
        name="presentation-slot-detail",
    ),
    # Whether finalists see the times yet.
    path(
        "finalists/presentation-times-shown/",
        PresentationTimesShownView.as_view(),
        name="presentation-times-shown",
    ),
    # What each finalist team said it can make.
    path(
        "finalists/presentation-responses/",
        PresentationResponsesView.as_view(),
        name="presentation-responses",
    ),
    # The time each finalist team is given.
    path(
        "finalists/presentation-allocation/<int:group_id>/",
        PresentationAllocationView.as_view(),
        name="presentation-allocation",
    ),
    # The slides each finalist team hands in for its presentation.
    path(
        "finalists/presentation-slides/",
        PresentationSlidesView.as_view(),
        name="presentation-slides",
    ),
    path(
        "finalists/presentation-slides/<int:group_id>/file/",
        PresentationSlidesFileView.as_view(),
        name="presentation-slides-file",
    ),

    # Send Test Email beside each email tab's preview.
    path("test-email/<str:kind>/", TestEmailView.as_view(), name="test-email"),

    # The Results section on a group's own page, for its members and admins.
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

    # Results emails to teams and supervisors, from the Release Results tab.
    path("results-email/", ResultsEmailSettingsView.as_view(), name="results-email"),
    path("results-email/preview/", ResultsEmailPreviewView.as_view(), name="results-email-preview"),
    path("results-email/send/", ResultsEmailSendView.as_view(), name="results-email-send"),
    path("results-email/sample-sheet/", ResultsSampleSheetView.as_view(), name="results-email-sample-sheet"),
    path(
        "results-email/supervisor-sheet/<int:supervisor_id>/",
        ResultsSupervisorSheetView.as_view(),
        name="results-email-supervisor-sheet",
    ),
]
