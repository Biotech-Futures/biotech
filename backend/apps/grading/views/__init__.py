from .analytics import ComponentAnalyticsView
from .component import ComponentMarkingListView
from .deadline import (
    GroupExtensionDetailView,
    GroupExtensionListView,
    SubmissionDeadlineView,
)
from .download import (
    AllSubmissionsDownloadView,
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .results import (
    ResultsEmailPreviewView,
    ResultsEmailSendView,
    ResultsEmailSettingsView,
    ResultsSampleSheetView,
)
from .finalist import (
    FinalistCandidatesView,
    FinalistEmailPreviewView,
    FinalistEmailSettingsView,
    FinalistListView,
    FinalistNotifyAllView,
    FinalistToggleView,
)
from .nonfinalist import (
    NonFinalistEmailPreviewView,
    NonFinalistEmailSendView,
    NonFinalistEmailView,
    NonSubmissionEmailPreviewView,
    NonSubmissionEmailSendView,
    NonSubmissionEmailView,
)
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupCategoriesView, GroupMarkingView
from .release import CertificatesReleaseView, MarksReleaseView
from .settings import (
    GradingSettingsView,
    TemplateDownloadView,
    TemplateScanView,
    TemplateTestRenderView,
)
from .student import MyCertificateView, MyGradesView, MySummaryView
from .test_email import TestEmailView
from .supervisor import SupervisorDownloadView, SupervisorGradesView
from .upload import BulkUploadMarksView

__all__ = [
    "AllSubmissionsDownloadView",
    "BulkUploadMarksView",
    "CertificatesReleaseView",
    "ComponentAnalyticsView",
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "FinalistCandidatesView",
    "FinalistEmailPreviewView",
    "ResultsEmailPreviewView",
    "ResultsEmailSendView",
    "ResultsEmailSettingsView",
    "ResultsSampleSheetView",
    "FinalistEmailSettingsView",
    "FinalistListView",
    "FinalistNotifyAllView",
    "FinalistToggleView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GradingSettingsView",
    "TemplateDownloadView",
    "TemplateScanView",
    "TemplateTestRenderView",
    "GroupDownloadView",
    "GroupExtensionDetailView",
    "GroupExtensionListView",
    "GroupCategoriesView",
    "GroupMarkingView",
    "MarksReleaseView",
    "SubmissionDeadlineView",
    "MyCertificateView",
    "MyGradesView",
    "MySummaryView",
    "NonFinalistEmailPreviewView",
    "NonFinalistEmailSendView",
    "NonFinalistEmailView",
    "NonSubmissionEmailPreviewView",
    "NonSubmissionEmailSendView",
    "NonSubmissionEmailView",
    "SupervisorDownloadView",
    "SupervisorGradesView",
    "TestEmailView",
]
