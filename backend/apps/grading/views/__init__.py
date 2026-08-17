from .component import ComponentMarkingListView
from .download import (
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupMarkingView
from .upload import BulkUploadMarksView

__all__ = [
    "BulkUploadMarksView",
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GroupDownloadView",
    "GroupMarkingView",
]
