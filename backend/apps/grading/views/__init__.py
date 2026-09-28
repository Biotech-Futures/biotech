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
from .results import ResultsEmailPreviewView, ResultsEmailSendView, ResultsEmailSettingsView
from .finalist import (
    FinalistCandidatesView,
    FinalistEmailPreviewView,
    FinalistEmailSettingsView,
    FinalistListView,
    FinalistNotifyAllView,
    FinalistToggleView,
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
    "SupervisorDownloadView",
    "SupervisorGradesView",
]
