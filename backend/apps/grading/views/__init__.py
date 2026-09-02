from .analytics import ComponentAnalyticsView
from .component import ComponentMarkingListView
from .deadline import SubmissionDeadlineView
from .download import (
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .finalist import (
    FinalistCandidatesView,
    FinalistListView,
    FinalistNotifyAllView,
    FinalistToggleView,
)
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupMarkingView
from .release import CertificatesReleaseView, MarksReleaseView
from .settings import GradingSettingsView
from .student import MyCertificateView, MyGradesView, MySummaryView
from .supervisor import SupervisorDownloadView, SupervisorGradesView
from .upload import BulkUploadMarksView

__all__ = [
    "BulkUploadMarksView",
    "CertificatesReleaseView",
    "ComponentAnalyticsView",
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "FinalistCandidatesView",
    "FinalistListView",
    "FinalistNotifyAllView",
    "FinalistToggleView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GradingSettingsView",
    "GroupDownloadView",
    "GroupMarkingView",
    "MarksReleaseView",
    "SubmissionDeadlineView",
    "MyCertificateView",
    "MyGradesView",
    "MySummaryView",
    "SupervisorDownloadView",
    "SupervisorGradesView",
]
