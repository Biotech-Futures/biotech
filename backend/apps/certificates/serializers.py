from rest_framework import serializers

from .models import MentorCertificate


class MentorCertificateSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SlugRelatedField(
        slug_field="name",
        read_only=True,
    )

    class Meta:
        model = MentorCertificate
        fields = [
            "id",
            "mentor_profile",
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
            "verified_at",
            "verified_by",
        ]
        read_only_fields = fields


class MentorCertificateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
            "mentor_profile",
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
        ]

    def validate_mentor_profile(self, value):
        request = self.context.get("request")
        if request and request.user:
            if not (request.user.is_staff or request.user.is_superuser):
                if hasattr(request.user, "mentorprofile"):
                    if value != request.user.mentorprofile:
                        raise serializers.ValidationError(
                            "You can only create certificates for yourself."
                        )
        return value

    def validate(self, data):
        certificate_type = data.get("certificate_type")
        certificate_number = data.get("certificate_number")

        if certificate_type:
            if certificate_type.requires_number and not certificate_number:
                raise serializers.ValidationError(
                    {
                        "certificate_number": (
                            f'Certificate type "{certificate_type.name}" requires a certificate number.'
                        )
                    }
                )

        return data


class MentorCertificateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
        ]


class AdminCertificateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
            "mentor_profile",
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
            "verified_at",
            "verified_by",
        ]
