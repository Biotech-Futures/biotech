from rest_framework import serializers
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'message', 'start_date', 'end_date', 'created_at', 'group', 'target_role', 'created_by']
        read_only_fields = ['id', 'created_at', 'created_by']

    def validate(self, attrs):
        start = attrs.get('start_date')
        end = attrs.get('end_date')
        group = attrs.get('group')
        target_role = attrs.get('target_role')

        if start and end and end <= start:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date.'
            })

        if group and target_role:
            raise serializers.ValidationError(
                'Cannot target both a group and a role. Choose one.'
            )

        return attrs
