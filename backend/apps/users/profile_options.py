from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404

from apps.groups.models import Countries, CountryStates
from .models import AreasOfInterest, StudentProfile, UserInterest
from .guardian_reminders import send_guardian_reminder

# The areas of interest registration offers, in its order (INTEREST_CATEGORIES
# in frontend/src/registration/registration.ts). Users 0023 loads them.
AREAS_OF_INTEREST = [
    "Biomedical Innovations",
    "Environmental Sustainability & Climate Tech",
    "Space & Astrobiology",
    "AI & Robotics and Smart Systems",
    "Nanotechnology & Materials Science",
    "Food & Agriculture Technology",
    "Neuroscience & Mental Health Tech",
    "Water & Energy Tech",
    "Ethical & Societal Impacts of Emerging Tech",
]


def registration_interests():
    """The registration areas as rows, leaving out any others in the table
    (old or seeded ones), so a student picks from what registering offered."""
    order = {name.lower(): index for index, name in enumerate(AREAS_OF_INTEREST)}
    rows = [
        row for row in AreasOfInterest.objects.values("id", "interest_desc")
        if row["interest_desc"].lower() in order
    ]
    return sorted(rows, key=lambda row: order[row["interest_desc"].lower()])


class StudentProfileOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        get_object_or_404(StudentProfile, user=request.user)
        return Response({
            "countries": list(Countries.objects.order_by("country_name").values("id", "country_name")),
            "regions": list(CountryStates.objects.order_by("state_name").values("id", "country_id", "state_name")),
            "interests": registration_interests(),
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
