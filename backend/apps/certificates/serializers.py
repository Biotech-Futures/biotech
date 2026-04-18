from rest_framework import serializers
<<<<<<< Updated upstream

from .models import MentorCertificate


class MentorCertificateSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SlugRelatedField(
        slug_field="name",
        read_only=True,
    )
=======
from django.utils import timezone
from .models import CertificateType, MentorCertificate


class CertificateTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateType
        fields = ['id', 'name', 'requires_number', 'requires_expiry']


class MentorCertificateSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SlugRelatedField(slug_field="name", read_only=True)
    verified = serializers.SerializerMethodField()
>>>>>>> Stashed changes

    class Meta:
        model = MentorCertificate
        fields = [
<<<<<<< Updated upstream
            "id",
            "mentor_profile",
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
            "verified_at",
            "verified_by_user",
        ]
        read_only_fields = fields
=======
            "id", "mentor_profile", "certificate_type",
            "certificate_number", "issued_by", "issued_at",
            "expires_at", "file_url", "verified_at", "verified_by", "verified",
        ]
        read_only_fields = fields

    def get_verified(self, obj):
        return obj.verified_at is not None
>>>>>>> Stashed changes


class MentorCertificateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
            "mentor_profile", "certificate_type",
            "certificate_number", "issued_by", "issued_at",
            "expires_at", "file_url",
        ]

    def validate_mentor_profile(self, value):
<<<<<<< Updated upstream
        request = self.context.get("request")
=======
        request = self.context.get('request')
>>>>>>> Stashed changes
        if request and request.user:
            if not (request.user.is_staff or request.user.is_superuser):
                if hasattr(request.user, "mentorprofile"):
                    if value != request.user.mentorprofile:
                        raise serializers.ValidationError(
                            "You can only create certificates for yourself."
                        )
        return value

    def validate(self, data):
<<<<<<< Updated upstream
        certificate_type = data.get("certificate_type")
        certificate_number = data.get("certificate_number")

        if certificate_type:
            if certificate_type.requires_number and not certificate_number:
                raise serializers.ValidationError(
                    {
                        "certificate_number": (
                            f'Certificate type "{certificate_type.name}" requires a certificate number.'
                        ),
                    }
                )

=======
        certificate_type = data.get('certificate_type')
        certificate_number = data.get('certificate_number')
        if certificate_type:
            if certificate_type.requires_number and not certificate_number:
                raise serializers.ValidationError({
                    'certificate_number': (
                        f'Certificate type "{certificate_type.name}" requires a certificate number.'
                    )
                })
>>>>>>> Stashed changes
        return data


class MentorCertificateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
            "certificate_type", "certificate_number",
            "issued_by", "issued_at", "expires_at", "file_url",
        ]


class AdminCertificateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorCertificate
        fields = [
<<<<<<< Updated upstream
            "mentor_profile",
            "certificate_type",
            "certificate_number",
            "issued_by",
            "issued_at",
            "expires_at",
            "file_url",
            "verified_at",
            "verified_by_user",
=======
            "mentor_profile", "certificate_type",
            "certificate_number", "issued_by", "issued_at",
            "expires_at", "file_url", "verified_at", "verified_by",
>>>>>>> Stashed changes
        ]
