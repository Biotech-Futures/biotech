"""Send Test Email on the email tabs: who each email can be tested as, and
sending one test to any address."""
from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView


from apps.common.rbac import IsStaffOrAdmin

from apps.services.system_email import sender_for

from ..services import test_email

logger = logging.getLogger(__name__)


class TestEmailSerializer(serializers.Serializer):
    recipient = serializers.CharField(error_messages={"blank": "Pick one from the list."})
    to = serializers.EmailField(
        error_messages={"invalid": "Enter a valid email address.", "blank": "Enter an email address."}
    )


class TestEmailView(APIView):
    """GET/POST /api/v1/management/test-email/<kind>/ — GET lists who the email
    can be tested as; POST sends it as ``recipient`` would get it to ``to``.
    The finalist and results emails also take the page's unsaved details,
    as their previews do. Nothing is recorded as sent."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, kind: str):
        if kind not in test_email.KINDS:
            return Response({"detail": "Unknown email."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"recipients": test_email.recipient_options(kind)})

    def post(self, request, kind: str):
        if kind not in test_email.KINDS:
            return Response({"detail": "Unknown email."}, status=status.HTTP_404_NOT_FOUND)
        serializer = TestEmailSerializer(data=request.data)
        if not serializer.is_valid():
            field = "recipient" if "recipient" in serializer.errors else "to"
            return Response({"detail": str(serializer.errors[field][0])}, status=status.HTTP_400_BAD_REQUEST)
        to = serializer.validated_data["to"]
        try:
            test_email.send_test(kind, serializer.validated_data["recipient"], to, request.data)
        except test_email.TestEmailError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except serializers.ValidationError:
            # An unsaved detail the page sent isn't valid, as its preview says.
            raise
        except Exception as exc:  # noqa: BLE001
            # Error type only: SMTP errors carry the recipient address.
            logger.error("test email: send failed kind=%s error=%s", kind, type(exc).__name__)
            return Response(
                {"detail": "The test email couldn't be sent. Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # Undeliverable mail comes back to the address it's sent from.
        sent_from = sender_for(test_email.KINDS[kind].email).address
        return Response({"sent_to": to, "sent_from": sent_from})
