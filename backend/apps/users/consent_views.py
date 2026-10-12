"""The public consent page's API: no login, the token in the emailed link is
the only credential."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import guardian_consent, guardian_details
from .views import _client_ip

# An unusable link is a 410 (it existed but is done), an unknown one a 404.
LINK_ERROR_STATUS = {"invalid": status.HTTP_404_NOT_FOUND}


class GuardianConsentSignSerializer(serializers.Serializer):
    guardianFullName = serializers.CharField(max_length=255, allow_blank=True)
    mediaConsent = serializers.BooleanField()
    signature = serializers.CharField()
    agreed = serializers.BooleanField()
    consentVersion = serializers.CharField(max_length=32)


def _link_error(error: guardian_consent.ConsentLinkError) -> Response:
    return Response(
        {"code": f"consent_link_{error.code}", "error": error.message},
        status=LINK_ERROR_STATUS.get(error.code, status.HTTP_410_GONE),
    )


class GuardianDetailsFormSerializer(serializers.Serializer):
    firstName = serializers.CharField(max_length=255)
    lastName = serializers.CharField(max_length=255)
    email = serializers.EmailField()


def _details_error(error: guardian_details.DetailsFormError) -> Response:
    return Response(
        {"code": f"details_link_{error.code}", "error": error.message},
        status=LINK_ERROR_STATUS.get(error.code, status.HTTP_410_GONE),
    )


class GuardianDetailsFormView(APIView):
    """GET the student a details form link is for; POST the guardian's name
    and email. No login, like the consent page."""

    permission_classes = [AllowAny]
    authentication_classes = []
    # Shares the consent page's per-IP limit.
    throttle_scope = "guardian_consent"

    @extend_schema(request=None, responses={200: None})
    def get(self, request, token):
        try:
            profile = guardian_details.open_details_form(token)
        except guardian_details.DetailsFormError as error:
            return _details_error(error)
        return Response({"studentName": guardian_details.student_name(profile)})

    @extend_schema(request=GuardianDetailsFormSerializer, responses={200: None})
    def post(self, request, token):
        serializer = GuardianDetailsFormSerializer(data=request.data)
        if not serializer.is_valid():
            # Name the field that's wrong, so the page can mark it.
            fields = sorted(serializer.errors)
            if fields == ["email"] and str(request.data.get("email") or "").strip():
                message = "Enter a full email address, like name@example.com."
            else:
                labels = {"firstName": "first name", "lastName": "last name", "email": "email"}
                message = f"Please enter the {' and '.join(labels[field] for field in fields)}."
            return Response(
                {"code": "details_form_incomplete", "error": message, "badFields": fields},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        try:
            profile = guardian_details.save_details_form(
                token, first_name=data["firstName"], last_name=data["lastName"], email=data["email"],
            )
        except guardian_details.DetailsFormError as error:
            return _details_error(error)
        except ValueError as error:
            return Response(
                {"code": "details_form_incomplete", "error": str(error), "badFields": ["email"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"studentName": guardian_details.student_name(profile), "email": profile.pg_email})


class GuardianConsentView(APIView):
    """GET the consent form behind a link; POST to sign it."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "guardian_consent"

    @extend_schema(request=None, responses={200: None})
    def get(self, request, token):
        try:
            consent_request = guardian_consent.open_request(token)
        except guardian_consent.ConsentLinkError as error:
            return _link_error(error)
        return Response(guardian_consent.form_for(consent_request))

    @extend_schema(request=GuardianConsentSignSerializer, responses={201: None})
    def post(self, request, token):
        serializer = GuardianConsentSignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"code": "consent_form_incomplete", "error": "Please complete every part of the form."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        if not data["agreed"]:
            return Response(
                {"code": "consent_form_incomplete", "error": "Please confirm the declaration before signing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            consent = guardian_consent.sign(
                token,
                full_name=data["guardianFullName"],
                media_consent=data["mediaConsent"],
                signature=data["signature"],
                version=data["consentVersion"],
                ip=_client_ip(request) or None,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except guardian_consent.ConsentLinkError as error:
            return _link_error(error)
        except ValueError as error:
            return Response(
                {"code": "consent_form_incomplete", "error": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"reference": consent.reference, "mediaConsent": consent.media_consent},
            status=status.HTTP_201_CREATED,
        )
