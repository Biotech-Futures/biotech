from django.urls import path

from .views import MessageViewSet

app_name = "chat"

message_list = MessageViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)

message_detail = MessageViewSet.as_view(
    {
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("groups/<str:group_id>/messages", message_list, name="group-messages"),
    path(
        "groups/<str:group_id>/messages/<int:pk>",
        message_detail,
        name="group-message-detail",
    ),
]
