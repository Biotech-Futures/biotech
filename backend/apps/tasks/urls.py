from django.urls import path
from . import views
from .views import TaskRetrieveview, TaskRetrieveUpdateView, MilestoneListHTMLView

urlpatterns = [
    path("api/v1/tasks/<int:pk>/", TaskRetrieveUpdateView.as_view(), name="task-detail"),
    path("api/v1/milestones/", MilestoneListHTMLView.as_view(), name="milestone-list")
]