from django.urls import path

from .views_admin import (
    SupportScopeRevokeView,
    SupportScopeView,
    TicketAdminAttachmentDownloadView,
    TicketAdminDetailView,
    TicketAssigneesView,
    TicketBulkAssignView,
    TicketHistoryView,
    TicketQueueView,
    TicketRegionsView,
    TicketSummaryView,
    TicketSupportMessageView,
)

# Mounted at /api/v1/admin/tickets/ from config.urls. No version segment here,
# and no "admin/" either — both belong to the mount point.
app_name = "tickets_admin"

urlpatterns = [
    path("", TicketQueueView.as_view(), name="queue"),
    path("summary/", TicketSummaryView.as_view(), name="summary"),
    path("assignees/", TicketAssigneesView.as_view(), name="assignees"),
    path("regions/", TicketRegionsView.as_view(), name="regions"),
    path("bulk-assign/", TicketBulkAssignView.as_view(), name="bulk-assign"),
    path("support-scope/", SupportScopeView.as_view(), name="support-scope"),
    path("support-scope/<int:user_id>/", SupportScopeRevokeView.as_view(),
         name="support-scope-revoke"),
    path("<int:ticket_id>/", TicketAdminDetailView.as_view(), name="detail"),
    path("<int:ticket_id>/history/", TicketHistoryView.as_view(), name="history"),
    path("<int:ticket_id>/messages/", TicketSupportMessageView.as_view(), name="messages"),
    path("<int:ticket_id>/attachments/<int:attachment_id>/",
         TicketAdminAttachmentDownloadView.as_view(), name="attachment-download"),
]
