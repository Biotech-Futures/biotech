from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "summary",
            "content",
            "author",
            "audience",
            "link",
            "createdAt",
            "updatedAt",
        ]


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "title",
            "summary",
            "content",
            "author",
            "audience",
            "link",
        ]
