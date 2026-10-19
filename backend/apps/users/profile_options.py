from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404

from apps.groups.models import Countries, CountryStates
from .models import AreasOfInterest, StudentProfile, UserInterest
from .guardian_reminders import send_guardian_reminder


class StudentProfileOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        get_object_or_404(StudentProfile, user=request.user)
        return Response({
            "countries": list(Countries.objects.order_by("country_name").values("id", "country_name")),
            "regions": list(CountryStates.objects.order_by("state_name").values("id", "country_id", "state_name")),
            "interests": list(AreasOfInterest.objects.order_by("interest_desc").values("id", "interest_desc")),
            "selected_interest_ids": list(UserInterest.objects.filter(user=request.user).values_list("interest_id", flat=True)),
        })


class GuardianInvitationThrottle(UserRateThrottle):
    scope = "guardian_invitation"
    rate = "5/hour"


class GuardianInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [GuardianInvitationThrottle]

    def post(self, request):
        get_object_or_404(StudentProfile, user=request.user)
        send_guardian_reminder(request.user.pk)
        return Response({"detail": "Guardian invitation sent."})
