from rest_framework import serializers

from .models import Resource


class ResourceListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing resources within the library.
    """

    url = serializers.URLField(source="file_url")
    coverImage = serializers.URLField(source="cover_image", allow_null=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "type",
            "role",
            "url",
            "coverImage",
        ]


class ResourceDetailSerializer(ResourceListSerializer):
    """
    Extends the list serializer to expose additional metadata.
    """

    class Meta(ResourceListSerializer.Meta):
        fields = ResourceListSerializer.Meta.fields + [
            "description",
            "download_count",
            "created_at",
            "updated_at",
        ]


class ResourceCreateSerializer(serializers.Serializer):
    """
    Serializer handling multi-part uploads for new resources.
    """

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(choices=Resource.TYPE_CHOICES)
    role = serializers.ChoiceField(choices=Resource.ROLE_CHOICES)
    file = serializers.FileField()


class ResourceCoverSerializer(serializers.Serializer):
    """
    Serializer for uploading resource cover images.
    """

    coverImage = serializers.ImageField()
