from django.urls import path

from .views import (
    TicketAttachmentDownloadView,
    TicketDetailView,
    TicketListCreateView,
    TicketMessageCreateView,
)

# Mounted at /api/v1/tickets/ from config.urls, so there is deliberately no
# version segment in here.
app_name = "tickets"

urlpatterns = [
    path("", TicketListCreateView.as_view(), name="ticket-list-create"),
    path("<int:ticket_id>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:ticket_id>/messages/", TicketMessageCreateView.as_view(), name="ticket-messages"),
    path(
        "<int:ticket_id>/attachments/<int:attachment_id>/",
        TicketAttachmentDownloadView.as_view(),
        name="ticket-attachment-download",
    ),
]
