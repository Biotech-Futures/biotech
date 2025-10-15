from rest_framework import serializers
from .models import MentorCertificate, CertificateType

class MentorCertificateSerializer(serializers.ModelSerializer):
    # Show the certificate type as a string (e.g., "WWCC") instead of numeric id
    certificate_type = serializers.SlugRelatedField(
        slug_field="certificate_type",
        read_only=True
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
            "verified",
        ]
        read_only_fields = fields  # read-only endpoint

class MentorCertificateCreateSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SlugRelatedField(
        slug_field="certificate_type",
        queryset=CertificateType.objects.all()
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
            "verified",
        ]

    def validate(self, data):
        cert_type = data.get("certificate_type")
        number = data.get("certificate_number")
        expiry = data.get("expires_at")

        if cert_type.requires_number and not number:
            raise serializers.ValidationError(
                f"Certificate type '{cert_type}' requires a certificate number."
            )
        if cert_type.requires_expiry and not expiry:
            raise serializers.ValidationError(
                f"Certificate type '{cert_type}' requires an expiry date."
            )
        return data