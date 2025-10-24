from rest_framework import serializers
from .models import Announcement
from apps.users.models import User


class AuthorSerializer(serializers.ModelSerializer):
    """Nested serializer for announcement author"""
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'author_name']
        read_only_fields = ['id', 'first_name', 'last_name', 'email', 'author_name']

    def get_author_name(self, obj):
        """Combine first and last name"""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.email  # Fallback to email if name not set


class AnnouncementListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing announcements.
    Used in list view - excludes full content field.
    """
    author = AuthorSerializer(read_only=True)
    author_name = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_datetime', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id',
            'title',
            'summary',
            'author',
            'author_name',
            'date',
            'created_datetime',
            'audience',
            'external_link',
            'internal_route',
            'is_pinned',
        ]
        read_only_fields = ['id', 'author', 'author_name', 'date', 'created_datetime']

    def get_author_name(self, obj):
        """Get author name for compatibility with frontend mock data"""
        if obj.author:
            if obj.author.first_name and obj.author.last_name:
                return f"{obj.author.first_name} {obj.author.last_name}"
            return obj.author.email
        return "Unknown"


class AnnouncementDetailSerializer(AnnouncementListSerializer):
    """
    Serializer for announcement detail view.
    Includes full content field.
    """
    class Meta(AnnouncementListSerializer.Meta):
        fields = AnnouncementListSerializer.Meta.fields + ['content', 'updated_datetime']
        read_only_fields = AnnouncementListSerializer.Meta.read_only_fields + ['updated_datetime']


class AnnouncementCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating announcements.
    """
    class Meta:
        model = Announcement
        fields = [
            'title',
            'summary',
            'content',
            'audience',
            'external_link',
            'internal_route',
            'is_pinned',
        ]

    def validate(self, attrs):
        """
        Validate that external_link and internal_route are not both set.
        """
        external_link = attrs.get('external_link')
        internal_route = attrs.get('internal_route')

        # Check if both are provided (in create) or being updated
        if external_link and internal_route:
            raise serializers.ValidationError({
                'external_link': 'Cannot set both external_link and internal_route. Choose one.',
                'internal_route': 'Cannot set both external_link and internal_route. Choose one.'
            })

        return attrs
