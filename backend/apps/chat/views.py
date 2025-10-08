from rest_framework import viewsets, permissions
from .models import Messages
from .serializers import MessageSerializer


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "attachments")
        )

    def perform_create(self, serializer):
        serializer.save(sender_user=self.request.user)
