from rest_framework import serializers

from .models import Event, EventRegistration


class EventListSerializer(serializers.ModelSerializer):
    coverImage = serializers.URLField(source="cover_image", allow_null=True, required=False)
    registerLink = serializers.URLField(source="register_link", allow_blank=True, required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    isRegistered = serializers.SerializerMethodField()
    registrationCount = serializers.IntegerField(source="registrations.count", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "date",
            "time",
            "location",
            "type",
            "coverImage",
            "registerLink",
            "capacity",
            "createdAt",
            "updatedAt",
            "isRegistered",
            "registrationCount",
        ]

    def get_isRegistered(self, obj: Event) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.registrations.filter(user=request.user).exists()


class EventDetailSerializer(EventListSerializer):
    longDescription = serializers.CharField(source="long_description", allow_blank=True)

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + ["longDescription"]


class EventCreateSerializer(serializers.ModelSerializer):
    coverImage = serializers.URLField(source="cover_image", allow_null=True, required=False)
    registerLink = serializers.URLField(source="register_link", allow_blank=True, required=False)
    longDescription = serializers.CharField(source="long_description", allow_blank=True, required=False)

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "longDescription",
            "date",
            "time",
            "location",
            "type",
            "coverImage",
            "registerLink",
            "capacity",
        ]


class EventCoverSerializer(serializers.Serializer):
    coverImage = serializers.ImageField()


class EventRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRegistration
        fields = ["id", "event", "user", "registered_at"]
        read_only_fields = fields
