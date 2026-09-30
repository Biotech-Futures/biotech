from .deadline import GroupExtensionDetailView, GroupExtensionListView, SubmissionDeadlineView
from .finalist import FinalistEmailPreviewView, FinalistEmailSettingsView, FinalistNotifyAllView
from .group_results import GroupResultsCertificateView, GroupResultsSummaryView, GroupResultsView
from .nonfinalist import (
    NonFinalistEmailPreviewView,
    NonFinalistEmailSendView,
    NonFinalistEmailView,
    NonSubmissionEmailPreviewView,
    NonSubmissionEmailSendView,
    NonSubmissionEmailView,
)
from .presentation import (
    PresentationAllocationView,
    PresentationResponsesView,
    PresentationSlidesFileView,
    PresentationSlidesView,
    PresentationSlotDetailView,
    PresentationSlotListView,
)
from .release import CertificatesReleaseView, MarksReleaseView
from .results import (
    ResultsEmailPreviewView,
    ResultsEmailSendView,
    ResultsEmailSettingsView,
    ResultsSampleSheetView,
    ResultsSupervisorSheetView,
)
from .settings import (
    GradingSettingsView,
    TemplateDownloadView,
    TemplatePeopleView,
    TemplateScanView,
    TemplateTestRenderView,
)
from .test_email import TestEmailView

__all__ = [
    "CertificatesReleaseView",
    "FinalistEmailPreviewView",
    "FinalistEmailSettingsView",
    "FinalistNotifyAllView",
    "GradingSettingsView",
    "GroupExtensionDetailView",
    "GroupExtensionListView",
    "GroupResultsCertificateView",
    "GroupResultsSummaryView",
    "GroupResultsView",
    "MarksReleaseView",
    "NonFinalistEmailPreviewView",
    "NonFinalistEmailSendView",
    "NonFinalistEmailView",
    "NonSubmissionEmailPreviewView",
    "NonSubmissionEmailSendView",
    "NonSubmissionEmailView",
    "PresentationAllocationView",
    "PresentationResponsesView",
    "PresentationSlidesFileView",
    "PresentationSlidesView",
    "PresentationSlotDetailView",
    "PresentationSlotListView",
    "ResultsEmailPreviewView",
    "ResultsEmailSendView",
    "ResultsEmailSettingsView",
    "ResultsSampleSheetView",
    "ResultsSupervisorSheetView",
    "SubmissionDeadlineView",
    "TemplateDownloadView",
    "TemplatePeopleView",
    "TemplateScanView",
    "TemplateTestRenderView",
    "TestEmailView",
]
