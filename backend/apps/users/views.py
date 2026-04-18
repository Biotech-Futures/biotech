from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.pagination import PageNumberPagination
<<<<<<< Updated upstream
from .models import User, StudentProfile, StudentInterest, AreasOfInterest, SupervisorProfile, StudentSupervisor
=======
from .models import (
    User, StudentProfile, StudentInterest, AreasOfInterest,
    SupervisorProfile, StudentSupervisor,
)
>>>>>>> Stashed changes
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Countries, CountryStates
from .serializers import (
    JoinPermissionRequestSerializer,
    UserRegisterRequestSerializer,
    UserSerializer,
    UserStatusPatchSerializer,
)

from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema


class UsersRetrieveView(generics.RetrieveAPIView):
    queryset = User.objects.select_related("track", "track__state")
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"


class UserPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class UserListHTMLView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    pagination_class = UserPagePagination
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/list.html"

    def get_queryset(self):
        queryset = User.objects.select_related("track", "track__state").all()
        is_active_param = self.request.query_params.get("is_active")
        if is_active_param is not None:
            queryset = queryset.filter(is_active=is_active_param.lower() in {"1", "true", "yes"})
        email_param = self.request.query_params.get("email")
        if email_param is not None:
            queryset = queryset.filter(email=email_param)
        return queryset


class UsersRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.select_related("track", "track__state")
    permission_classes = [permissions.AllowAny]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"

    def get_serializer_class(self):
        return UserSerializer

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data = request.data
        if "is_active" in data:
            user.is_active = data["is_active"]
            user.save(update_fields=["is_active"])

        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()
            with transaction.atomic():
                RoleAssignmentHistory.objects.create(
                    user=user, role=role,
                    valid_from=now + timedelta(seconds=1),
                    valid_to=now + timedelta(weeks=104),
                )

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class MeRetrieveView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data = request.data
        if "is_active" in data:
            user.is_active = data["is_active"]
            user.save(update_fields=["is_active"])

        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()
            with transaction.atomic():
                RoleAssignmentHistory.objects.create(
                    user=user, role=role,
                    valid_from=now + timedelta(seconds=1),
                    valid_to=now + timedelta(weeks=6),
                )

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class UserRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegisterRequestSerializer

    @extend_schema(request=UserRegisterRequestSerializer, responses={200: UserRegisterRequestSerializer})
    @transaction.atomic
    def post(self, request):
        data = request.data
        databody = data["body"]

<<<<<<< Updated upstream
        country, _ = Countries.objects.get_or_create(country_name=databody["Country"])

        if databody["Country"] == "Australia":
            user_country, _ = CountryStates.objects.get_or_create(country=country, state_name=databody["Region"])
            if databody["Region"] == "NSW":
                user_track, _ = Tracks.objects.get_or_create(track_code="AUS-NSW", state=user_country)
            elif databody["Region"] == "QLD":
                user_track, _ = Tracks.objects.get_or_create(track_code="AUS-QLD", state=user_country)
            elif databody["Region"] == "VIC":
                user_track, _ = Tracks.objects.get_or_create(track_code="AUS-VIC", state=user_country)
            elif databody["Region"] == "WA":
                user_track, _ = Tracks.objects.get_or_create(track_code="AUS-WA", state=user_country)
            else:
                user_track, _ = Tracks.objects.get_or_create(track_code="Global", state=user_country)
        else:
            user_country, _ = CountryStates.objects.get_or_create(country=country, state_name=databody["Country"])
            if databody["Country"] == "Brazil":
                user_track, _ = Tracks.objects.get_or_create(track_code="Brazil", state=user_country)
            else:
                user_track, _ = Tracks.objects.get_or_create(track_code="Global", state=user_country)

        user = User.objects.create_user(
            email=databody["Title"],
            track=user_track,
            first_name=databody["FirstName"],
            last_name=databody["Surname"],
        )
=======
        user = User.objects.create_user(email=databody["Title"])
        user.first_name = databody["FirstName"]
        user.last_name = databody["Surname"]

        country, _ = Countries.objects.get_or_create(country_name=databody["Country"])

        if databody["Country"] == "Australia":
            user_country, _ = CountryStates.objects.get_or_create(
                country=country, state_name=databody["Region"]
            )
            region = databody.get("Region", "")
            code_map = {"NSW": "AUS-NSW", "QLD": "AUS-QLD", "VIC": "AUS-VIC", "WA": "AUS-WA"}
            track_code = code_map.get(region, "AUS-OTHER")
            user_track, _ = Tracks.objects.get_or_create(track_code=track_code, state=user_country)
        else:
            user_country, _ = CountryStates.objects.get_or_create(
                country=country, state_name=databody["Country"]
            )
            track_code = "Brazil" if databody["Country"] == "Brazil" else "Global"
            user_track, _ = Tracks.objects.get_or_create(track_code=track_code, state=user_country)

        user.track = user_track
        user.save()
>>>>>>> Stashed changes

        now = timezone.now()
        role = get_object_or_404(Roles, pk=4)
        RoleAssignmentHistory.objects.create(
            user=user, role=role,
            valid_from=now + timedelta(seconds=1),
            valid_to=now + timedelta(weeks=6),
        )

<<<<<<< Updated upstream
        #supervisorprofile check
        sup, sup_created = User.objects.get_or_create(
            email=databody["SupervisorEmail"],
            defaults={
                "track": user_track,
                "first_name": databody["SupervisorFirstName"],
                "last_name": databody["SupervisorSurname"],
            },
        )
        if not sup_created:
            sup.track = user_track
            sup.first_name = databody["SupervisorFirstName"]
            sup.last_name = databody["SupervisorSurname"]
            sup.save(update_fields=["track", "first_name", "last_name"])
=======
        sup, _ = User.objects.get_or_create(email=databody["SupervisorEmail"])
        sup.first_name = databody["SupervisorFirstName"]
        sup.last_name = databody["SupervisorSurname"]
        sup.save()
>>>>>>> Stashed changes
        sup_role = get_object_or_404(Roles, pk=2)
        RoleAssignmentHistory.objects.create(
            user=sup, role=sup_role,
            valid_from=now + timedelta(seconds=1),
            valid_to=now + timedelta(weeks=6),
        )

        supprof, _ = SupervisorProfile.objects.get_or_create(
            user=sup, school_name=databody["SchoolName"]
        )

        sp = StudentProfile.objects.create(
            user=user,
            supervisor=supprof,
            school_name=databody["SchoolName"],
            year_level=int(databody["YearLevel"]),
        )

        StudentSupervisor.objects.create(student_user=sp, supervisor_user=supprof)

        StudentInterest.objects.create(
            student_user=sp,
<<<<<<< Updated upstream
            supervisor_user=supprof,
        )

        #interest
        StudentInterest.objects.create(
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
            student_profile=sp,
=======
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
>>>>>>> Stashed changes
        )
        return Response(data["body"])


class ReceiveJoinPermissionView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = JoinPermissionRequestSerializer

    @extend_schema(request=JoinPermissionRequestSerializer, responses={200: JoinPermissionRequestSerializer})
    @transaction.atomic
    def post(self, request):
        data = request.data
        databody = data["body"]

        user = get_object_or_404(User, email=databody["Email"])
        sp = get_object_or_404(StudentProfile, user=user)

        sp.join_permission_received = True
        sp.join_permission_response_id = databody["ResponseID"]
        sp.save()

        return Response(data["body"])
