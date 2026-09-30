from .analytics import ComponentAnalyticsView
from .component import ComponentMarkingListView
from .download import (
    AllSubmissionsDownloadView,
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .finalist import FinalistCandidatesView, FinalistListView, FinalistToggleView
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupCategoriesView, GroupMarkingView
from .group_results import GroupResultsCertificateView, GroupResultsSummaryView, GroupResultsView
from .student import MyCertificateView, MyGradesView, MySummaryView
from .supervisor import SupervisorDownloadView, SupervisorGradesView
from .upload import BulkUploadMarksView

__all__ = [
    "AllSubmissionsDownloadView",
    "BulkUploadMarksView",
    "ComponentAnalyticsView",
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "FinalistCandidatesView",
    "FinalistListView",
    "FinalistToggleView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GroupCategoriesView",
    "GroupDownloadView",
    "GroupMarkingView",
    "GroupResultsCertificateView",
    "GroupResultsSummaryView",
    "GroupResultsView",
    "MyCertificateView",
    "MyGradesView",
    "MySummaryView",
    "SupervisorDownloadView",
    "SupervisorGradesView",
]
