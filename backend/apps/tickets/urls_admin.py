from django.urls import path

from .views_admin import (
    SupportScopeRevokeView,
    TicketDeleteView,
    SupportScopeView,
    TicketAdminAttachmentDownloadView,
    TicketAdminDetailView,
    TicketAnalyticsView,
    TicketAssigneesView,
    TicketAuditExportView,
    TicketAuditView,
    TicketBulkAssignView,
    TicketDigestSendView,
    TicketHistoryView,
    TicketQueueExportView,
    TicketQueueView,
    TicketRegionsView,
    TicketScreeningReviewView,
    TicketSummaryView,
    TicketSupportMessageView,
)

# Mounted at /api/v1/admin/tickets/ from config.urls. No version segment here,
# and no "admin/" either — both belong to the mount point.
app_name = "tickets_admin"

urlpatterns = [
    path("", TicketQueueView.as_view(), name="queue"),
    # The queue itself as an Excel file; takes the queue's own filters.
    path("export/", TicketQueueExportView.as_view(), name="export"),
    path("summary/", TicketSummaryView.as_view(), name="summary"),
    path("assignees/", TicketAssigneesView.as_view(), name="assignees"),
    path("regions/", TicketRegionsView.as_view(), name="regions"),
    path("bulk-assign/", TicketBulkAssignView.as_view(), name="bulk-assign"),
    # The scheduler's door, with its own token instead of a session.
    path("digest/send/", TicketDigestSendView.as_view(), name="digest-send"),
    # Before the <int:ticket_id> patterns, like every other literal segment
    # here. "audit" is not a number so it could not be captured by them, but
    # keeping the literals together is what stops the next one being added
    # below the catch-alls.
    path("analytics/", TicketAnalyticsView.as_view(), name="analytics"),
    path("audit/", TicketAuditView.as_view(), name="audit"),
    # The Audit tab as an Excel file; takes the tab's own filters (C-26).
    path("audit/export/", TicketAuditExportView.as_view(), name="audit-export"),
    path("support-scope/", SupportScopeView.as_view(), name="support-scope"),
    path("support-scope/<int:user_id>/", SupportScopeRevokeView.as_view(),
         name="support-scope-revoke"),
    path("<int:ticket_id>/", TicketAdminDetailView.as_view(), name="detail"),
    path("<int:ticket_id>/delete/", TicketDeleteView.as_view(), name="delete"),
    path("<int:ticket_id>/history/", TicketHistoryView.as_view(), name="history"),
    path(
        "<int:ticket_id>/screening-review/",
        TicketScreeningReviewView.as_view(),
        name="screening-review",
    ),
    path("<int:ticket_id>/messages/", TicketSupportMessageView.as_view(), name="messages"),
    path("<int:ticket_id>/attachments/<int:attachment_id>/",
         TicketAdminAttachmentDownloadView.as_view(), name="attachment-download"),
]
