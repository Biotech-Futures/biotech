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


class MentorCertificateCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating mentor certificates.
    Excludes read-only fields like 'id' and 'verified'.
    Mentors cannot set the 'verified' flag - only admins can.
    """
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
        """
        Ensure mentors can only create certificates for themselves (not admins)
        """
        request = self.context.get('request')
        if request and request.user:
            # If user is not admin, they can only create certificates for themselves
            if not (request.user.is_staff or request.user.is_superuser):
                if hasattr(request.user, 'mentorprofile'):
                    if value != request.user.mentorprofile:
                        raise serializers.ValidationError(
                            "You can only create certificates for yourself."
                        )
        return value
    
    def validate(self, data):
        """
        Validate certificate type requirements (number only).
        Expiry dates are optional - certificates can be indefinite or have expiry dates.
        Admin verification handles all validation including expiry dates.
        """
        certificate_type = data.get('certificate_type')
        certificate_number = data.get('certificate_number')
        
        if certificate_type:
            # Check if certificate type requires a number
            if certificate_type.requires_number and not certificate_number:
                raise serializers.ValidationError({
                    'certificate_number': f'Certificate type "{certificate_type.certificate_type}" requires a certificate number.'
                })
            
            # Note: No expiry validation needed - certificates can be indefinite
            # Admin verification will handle expiry date validation when needed
        
        return data


class MentorCertificateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating mentor certificates.
    Mentors can update their certificate details but NOT the 'verified' flag.
    Admins can update everything including 'verified'.
    """
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
        # mentor_profile is not editable after creation


class AdminCertificateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for admins to update certificates.
    Admins can update all fields including 'verified'.
    """
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
            "verified",
        ]

