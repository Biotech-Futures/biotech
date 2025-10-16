from rest_framework import serializers
from .models import MentorCertificate


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

