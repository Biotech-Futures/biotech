from .component import ComponentMarkingListView
from .download import (
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .finalist import FinalistListView, FinalistToggleView
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupMarkingView
from .release import MarksReleaseView
from .settings import GradingSettingsView
from .student import MyCertificateView, MyGradesView, MySummaryView
from .supervisor import SupervisorDownloadView, SupervisorGradesView
from .upload import BulkUploadMarksView

__all__ = [
    "BulkUploadMarksView",
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "FinalistListView",
    "FinalistToggleView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GradingSettingsView",
    "GroupDownloadView",
    "GroupMarkingView",
    "MarksReleaseView",
    "MyCertificateView",
    "MyGradesView",
    "MySummaryView",
    "SupervisorDownloadView",
    "SupervisorGradesView",
]
