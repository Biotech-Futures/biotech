from rest_framework import serializers


class DashboardNextEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_name = serializers.CharField()
    start_datetime = serializers.DateTimeField()
    location = serializers.CharField(allow_null=True, allow_blank=True)
    link = serializers.URLField(allow_null=True, allow_blank=True)
    is_virtual = serializers.BooleanField()
