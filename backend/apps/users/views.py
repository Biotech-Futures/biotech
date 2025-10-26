from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from django.db import transaction
from rest_framework import serializers, generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.pagination import PageNumberPagination
from.models import User, StudentProfile, StudentInterest, AreasOfInterest, SupervisorProfile, RelationshipType, StudentSupervisor
from apps.groups.models import GroupMembers
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Countries, CountryStates
from .serializers import UserSerializer, UserStatusPatchSerializer
from django.db.models import Exists, OuterRef, Q, Count
from .services.permission import IsAdminOrSupervisor

from rest_framework.views import APIView

# Create your views here.
#Issue 41
class UsersRetrieveView(generics.RetrieveAPIView):
    queryset = User.objects.select_related("track","state")
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    # renderer_classes = [JSONRenderer]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"

class UserPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100

#Issue 42
class UserListHTMLView(generics.ListAPIView):
    # queryset = Users.objects.select_related("track", "state")
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    pagination_class = UserPagePagination
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/list.html"

    def get_queryset(self):
        queryset = User.objects.all()
        status_param = self.request.query_params.get("status")
        if status_param is not None:
            queryset = queryset.filter(status=status_param)
        email_param = self.request.query_params.get("email")
        if email_param is not None:
            queryset = queryset.filter(email=email_param)
        return queryset
    
#issue 43
class UsersRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.select_related("track","state")
    permission_classes = [permissions.AllowAny]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"

    def get_serializer_class(self):
        return UserSerializer

    
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data=request.data
        if "status" in data:
            user.status = data["status"]
            user.save(update_fields=["status"])

        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()

            with transaction.atomic():
                # RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now, valid_to__gte=now).update(valid_to=now-timedelta(seconds=1))
                RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=104))

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    
#issue 40
class MeRetrieveView(generics.RetrieveAPIView):
    # queryset = User.objects.select_related("track","state")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_object(self):
        obj = self.request.user
        return obj
    
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data=request.data
        if "status" in data:
            user.status = data["status"]
            user.save(update_fields=["status"])

        #for role_id, 3 is mentor, 4 is student, 1 is admin, 2 is supervisor
        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()

            with transaction.atomic():
                # RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now, valid_to__gte=now).update(valid_to=now-timedelta(seconds=1))
                RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    
class UserRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        data = request.data
        databody = data["body"]

        #users table creation   
        user = User.objects.create_user(email=databody["Title"])
        user.first_name = databody["FirstName"]
        user.last_name = databody["Surname"]

        country, created = Countries.objects.get_or_create(country_name=databody["Country"])
        
        if databody["Country"] == "Australia":
            user_country, s_created = CountryStates.objects.get_or_create(country=country, state_name=databody["Region"])
            if databody["Region"] == "NSW":
                user_track, t_created = Tracks.objects.get_or_create(track_name="AUS-NSW", state=user_country)
            elif databody["Region"] == "QLD":
                user_track, t_created = Tracks.objects.get_or_create(track_name="AUS-QLD", state=user_country)
            elif databody["Region"] == "VIC":
                user_track, t_created = Tracks.objects.get_or_create(track_name="AUS-VIC", state=user_country)
            elif databody["Region"] == "WA":
                user_track, t_created = Tracks.objects.get_or_create(track_name="AUS-WA", state=user_country)
        else:
            user_country, s_created = CountryStates.objects.get_or_create(country=country, state_name=databody["Country"])
            if databody["Country"] == "Brazil":
                #TODO: align brazil and global names to tracks
                user_track, t_created = Tracks.objects.get_or_create(track_name="Brazil", state=user_country)
            else:
                user_track, t_created = Tracks.objects.get_or_create(track_name="Global", state=user_country)
        user.state = user_country
        user.track = user_track
    

        user.save()

        #roleassignmenthistory creation
        now = timezone.now()
        role = get_object_or_404(Roles, pk=4)
        rah = RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))

        #supervisorprofile check
        sup, sup_created = User.objects.get_or_create(email=databody["SupervisorEmail"])
        sup.first_name = databody["SupervisorFirstName"]
        sup.last_name = databody["SupervisorSurname"]
        sup.save()
        sup_role = get_object_or_404(Roles, pk=2)
        sup_rah = RoleAssignmentHistory.objects.create(user=sup, role=sup_role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))
        
        #relationshiptype check
        if databody["SupervisorEmail"] == databody["GuardianEmail"]:
            rel, rel_created = RelationshipType.objects.get_or_create(relationship_type="Guardian")
            pgflag = True
        else:
            rel, rel_created = RelationshipType.objects.get_or_create(relationship_type="Supervisor")
            pgflag = False

        #supervisorprofile creation
        supprof, supprof_created = SupervisorProfile.objects.get_or_create(user=sup, school_name=databody["SchoolName"])

        #studentprofile creation
        sp = StudentProfile.objects.create(
            user=user,
            pg_first_name=databody["GuardianName"],
            pg_last_name=databody["GuardianSurname"],
            parent_guardian_flag=True,
            supervisor=supprof,
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
            school_name=databody["SchoolName"],
            year_lvl=databody["YearLevel"]
        )

        #studentsupervisor creation
        ss = StudentSupervisor.objects.create(
            student_user=sp,
            supervisor_user=supprof,
            relationship_type=rel
        )

        #interest
        si = StudentInterest.objects.create(
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
            user=user
        )
        return Response(data["body"])
    
#issue 128
class ReceiveJoinPermissionView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        data = request.data
        databody = data["body"]

        # find the correct user
        user = get_object_or_404(User, email=databody["Email"])

        sp = get_object_or_404(StudentProfile, user=user)

        sp.has_join_permission = True
        sp.joinperm_responseID = databody["ResponseID"]
        sp.save()

        return Response(data["body"])

# issue 184


def _apply_common_filters(qs, request, role: str):
    """
    Shared filters:
      - track: accepts ID or exact track_name (case-insensitive)
      - school: StudentProfile.school_name (students) / MentorProfile.institution (mentors)
      - q: free-text over first_name, last_name, email
    """
    track = request.query_params.get("track")
    school = request.query_params.get("school")
    query = request.query_params.get("q")

    if track:
        if track.isdigit():
            qs = qs.filter(track_id=int(track))
        else:
            qs = qs.filter(track__track_name__iexact=track)

    if school:
        if role == "student":
            qs = qs.filter(studentprofile__school_name__icontains=school)
        else:
            qs = qs.filter(mentorprofile__institution__icontains=school)

    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    # Ensure the filtered queryset is returned to callers
    return qs

# GET /api/v1/groups/unallocated/students/


class UnallocatedStudentsListView(generics.ListAPIView):
    """
    Lists Users who have a StudentProfile and are not in any group.
    Supports ordering: ?ordering=last_name,-email,studentprofile__school_name,track__track_name,...
    """

    serializer_class = UserSerializer
    permission_classes = [IsAdminOrSupervisor]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        "first_name",
        "last_name",
        "email",
        "track_name",
        "school_name",
        "year_lvl",
    ]
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        gm_exists = GroupMembers.objects.filter(user_id=OuterRef("pk"))
        qs = (
            User.objects
            .filter(studentprofile__isnull=False, status=True)
            .annotate(is_member=Exists(gm_exists))
            .filter(is_member=False)
            .select_related("track", "state")
            .select_related("studentprofile")
        )
        return _apply_common_filters(qs, self.request, role="student")

# GET /api/v1/groups/unallocated/mentors/


class UnallocatedMentorsListView(generics.ListAPIView):
    """
    Lists Users who have a MentorProfile and are not in any group.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrSupervisor]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        "first_name",
        "last_name",
        "email",
        "track_name",
        "institution",
        "max_grp_cnt",
    ]
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        gm_exists = GroupMembers.objects.filter(user_id=OuterRef("pk"))
        qs = (
            User.objects
            .filter(mentorprofile__isnull=False, status=True)
            .annotate(is_member=Exists(gm_exists))
            .filter(is_member=False)
            .select_related("track", "state")
            .select_related("mentorprofile")
        )
        return _apply_common_filters(qs, self.request, role="mentor")

# GET /api/v1/groups/unallocated/summary/


class UnallocatedSummaryView(APIView):
    """
    Returns overall and breakdown counts for unallocated students and mentors.
    Applies same filters as the list endpoints.
    """
    permission_classes = [IsAdminOrSupervisor]

    def get(self, request):
        gm_exists = GroupMembers.objects.filter(user_id=OuterRef("pk"))

        students = (
            User.objects
            .filter(studentprofile__isnull=False)
            .annotate(is_member=Exists(gm_exists))
            .filter(is_member=False)
        )
        students = _apply_common_filters(students, request, role="student")

        mentors = (
            User.objects
            .filter(mentorprofile__isnull=False)
            .annotate(is_member=Exists(gm_exists))
            .filter(is_member=False)
        )
        mentors = _apply_common_filters(mentors, request, role="mentor")

        students_total = students.count()
        mentors_total = mentors.count()

        students_by_school = (
            students.values("studentprofile__school_name")
            .annotate(count=Count("id"))
            .order_by("studentprofile__school_name")
        )
        mentors_by_institution = (
            mentors.values("mentorprofile__institution")
            .annotate(count=Count("id"))
            .order_by("mentorprofile__institution")
        )

        students_by_track = (
            students.values("track_id", "track__track_name")
            .annotate(count=Count("id"))
            .order_by("track__track_name")
        )
        mentors_by_track = (
            mentors.values("track_id", "track__track_name")
            .annotate(count=Count("id"))
            .order_by("track__track_name")
        )

        return Response({
            "students": {
                "total": students_total,
                "by_school": list(students_by_school),
                "by_track": list(students_by_track),
            },
            "mentors": {
                "total": mentors_total,
                "by_institution": list(mentors_by_institution),
                "by_track": list(mentors_by_track),
            }
        })
