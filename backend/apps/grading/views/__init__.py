from .component import ComponentMarkingListView
from .download import (
    ComponentDownloadView,
    GradingJobDetailView,
    GradingJobDownloadView,
    GroupDownloadView,
)
from .grade import GradeBulkView, GradeUpdateView
from .group import GroupMarkingView

__all__ = [
    "ComponentDownloadView",
    "ComponentMarkingListView",
    "GradeBulkView",
    "GradeUpdateView",
    "GradingJobDetailView",
    "GradingJobDownloadView",
    "GroupDownloadView",
    "GroupMarkingView",
]
