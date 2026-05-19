from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from.models import User, StudentProfile, UserInterest, AreasOfInterest, SupervisorProfile, StudentSupervisor
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Countries, CountryStates, Groups
from apps.events.models import Events
from apps.matching_runtime.models import MatchRecommendation
from .serializers import (
    AdminOperationsSummarySerializer,
    BulkUserStatusSerializer,
    BulkUserTrackSerializer,
    JoinPermissionRequestSerializer,
    UserRegisterRequestSerializer,
    UserSerializer,
    UserStatusPatchSerializer,
)
from .utils.admin_scope import can_admin_track, get_admin_track_ids, is_operational_admin
from config.errors import (
    AccountInactive,
    AdminScopeForTrackRequired,
    AdminScopeForUserRequired,
    InvalidCredentials,
    MissingUsers,
    OperationalAdminRequired,
    TooManyFailedAttempts,
)

class PasswordLoginBodySerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class PasswordLoginView(APIView):
    """ Unified Session-based Password Login with Brute-Force lockout """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    @extend_schema(request=PasswordLoginBodySerializer, responses={200: UserSerializer})
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Brute-force guard: 5 failed attempts → 5 min lockout per email.
        cache_key = f"pwd_login_attempts:{email}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            raise TooManyFailedAttempts()

        # Single bcrypt check (was being done twice — once here, once inside
        # authenticate() — adding ~300ms per login).
        user_obj = User.objects.filter(email=email).first()
        if user_obj is None or not user_obj.check_password(password):
            cache.set(cache_key, attempts + 1, 300)
            raise InvalidCredentials()

        if user_obj.account_status in ['suspended', 'deactivated']:
            raise AccountInactive()

        # Bypass authenticate()'s second bcrypt by setting the backend manually;
        # login() only needs to know which auth backend to associate with the session.
        # Path must match AUTHENTICATION_BACKENDS so the session resolves
        # back to a real backend on subsequent requests.
        user_obj.backend = 'apps.users.backends.CachedModelBackend'
        login(request, user_obj)
        cache.delete(cache_key)
        return Response(UserSerializer(user_obj).data)

# Create your views here.
#Issue 41
class UsersRetrieveView(generics.RetrieveAPIView):
    queryset = User.objects.select_related("track", "track__state")
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
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    pagination_class = UserPagePagination
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/list.html"

    def get_queryset(self):
        queryset = User.objects.select_related("track", "track__state").order_by("id")
        account_status_param = self.request.query_params.get("account_status")
        if account_status_param is not None:
            queryset = queryset.filter(account_status=account_status_param.lower())
        email_param = self.request.query_params.get("email")
        if email_param is not None:
            queryset = queryset.filter(email=email_param)
        return queryset
    
#issue 43
class UsersRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.select_related("track", "track__state")
    permission_classes = [permissions.AllowAny]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"

    def get_serializer_class(self):
        return UserSerializer

    
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data=request.data
        if "account_status" in data:
            user.apply_account_status(data["account_status"])

        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()

            with transaction.atomic():
                # RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now, valid_to__gte=now).update(valid_to=now-timedelta(seconds=1))
                RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=104))

        if "timezone" in data:
            serializer = UserSerializer(user, data={"timezone": data["timezone"]}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

#issue 40
class MeRetrieveView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_object(self):
        obj = self.request.user
        return obj

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data=request.data
        if "account_status" in data:
            user.apply_account_status(data["account_status"])

        #for role_id, 3 is mentor, 4 is student, 1 is admin, 2 is supervisor
        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()

            with transaction.atomic():
                # RoleAssignmentHistory.objects.filter(user=user, valid_from__lte=now, valid_to__gte=now).update(valid_to=now-timedelta(seconds=1))
                RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))

        if "timezone" in data:
            serializer = UserSerializer(user, data={"timezone": data["timezone"]}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    
class UserRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegisterRequestSerializer

    @extend_schema(request=UserRegisterRequestSerializer, responses={200: UserRegisterRequestSerializer})
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
                user_track, t_created = Tracks.objects.get_or_create(track_name="Brazil", state=user_country)
            else:
                user_track, t_created = Tracks.objects.get_or_create(track_name="Global", state=user_country)
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
        
        if databody["SupervisorEmail"] == databody["GuardianEmail"]:
            pgflag = True
        else:
            pgflag = False

        #supervisorprofile creation
        supprof, supprof_created = SupervisorProfile.objects.get_or_create(user=sup, school_name=databody["SchoolName"])

        #studentprofile creation
        sp = StudentProfile.objects.create(
            user=user,
            pg_first_name=databody["GuardianName"],
            pg_last_name=databody["GuardianSurname"],
            parent_guardian_flag=pgflag,
            supervisor=supprof,
            school_name=databody["SchoolName"],
            year_lvl=databody["YearLevel"]
        )

        #studentsupervisor creation
        ss = StudentSupervisor.objects.create(
            student_user=sp,
            supervisor_user=supprof,
        )

        #interest
        si = UserInterest.objects.create(
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
            user=user
        )
        return Response(data["body"])
    
#issue 128
class ReceiveJoinPermissionView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = JoinPermissionRequestSerializer

    @extend_schema(request=JoinPermissionRequestSerializer, responses={200: JoinPermissionRequestSerializer})
    @transaction.atomic
    def post(self, request):
        data = request.data
        databody = data["body"]

        #find the correct user
        user = get_object_or_404(User, email=databody["Email"])
        
        sp = get_object_or_404(StudentProfile, user=user)

        sp.has_join_permission = True
        sp.joinperm_responseID = databody["ResponseID"]
        sp.save()

        return Response(data["body"])


class AdminOperationalSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]
    serializer_class = AdminOperationsSummarySerializer

    @extend_schema(request=None, responses={200: AdminOperationsSummarySerializer})
    def get(self, request):
        if not is_operational_admin(request.user):
            raise OperationalAdminRequired()

        track_scope = get_admin_track_ids(request.user)
        user_queryset = User.objects.all()
        group_queryset = Groups.objects.filter(deleted_at__isnull=True)
        recommendation_queryset = MatchRecommendation.objects.filter(accepted=False)
        event_queryset = Events.objects.filter(deleted_at__isnull=True, start_datetime__gte=timezone.now())

        if track_scope is not None:
            user_queryset = user_queryset.filter(track_id__in=track_scope)
            group_queryset = group_queryset.filter(track_id__in=track_scope)
            recommendation_queryset = recommendation_queryset.filter(group__track_id__in=track_scope)
            event_queryset = event_queryset.filter(Q(track_id__in=track_scope) | Q(track__isnull=True))

        groups_without_mentor = group_queryset.annotate(
            active_mentor_count=Count(
                "groupmembership",
                filter=Q(
                    groupmembership__membership_role__iexact="mentor",
                    groupmembership__left_at__isnull=True,
                ),
            )
        ).filter(active_mentor_count=0).count()

        payload = {
            "track_scope": [] if track_scope is None else list(track_scope),
            "active_users": user_queryset.filter(account_status=User.AccountStatus.ACTIVE).count(),
            "invited_or_pending_users": user_queryset.filter(
                account_status__in=[User.AccountStatus.INVITED, User.AccountStatus.PENDING]
            ).count(),
            "suspended_or_deactivated_users": user_queryset.filter(
                account_status__in=[User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED]
            ).count(),
            "active_groups": group_queryset.count(),
            "groups_without_mentor": groups_without_mentor,
            "unassigned_match_recommendations": recommendation_queryset.count(),
            "upcoming_events": event_queryset.count(),
        }
        return Response(AdminOperationsSummarySerializer(payload).data)


class BulkUserStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(request=BulkUserStatusSerializer, responses={200: UserSerializer(many=True)})
    @transaction.atomic
    def post(self, request):
        if not is_operational_admin(request.user):
            raise OperationalAdminRequired()

        serializer = BulkUserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data["user_ids"]
        users = list(User.objects.filter(id__in=user_ids).order_by("id"))
        found_ids = {user.id for user in users}
        missing_ids = [user_id for user_id in user_ids if user_id not in found_ids]
        if missing_ids:
            raise MissingUsers(missing_ids)

        target_status = serializer.validated_data["account_status"]
        for user in users:
            if user.track_id and not can_admin_track(request.user, user.track_id):
                raise AdminScopeForUserRequired(user.id)
            user.apply_account_status(target_status)

        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)


class BulkUserTrackAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(request=BulkUserTrackSerializer, responses={200: UserSerializer(many=True)})
    @transaction.atomic
    def post(self, request):
        if not is_operational_admin(request.user):
            raise OperationalAdminRequired()

        serializer = BulkUserTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_track = serializer.validated_data["track"]
        if not can_admin_track(request.user, target_track):
            raise AdminScopeForTrackRequired()

        user_ids = serializer.validated_data["user_ids"]
        users = list(User.objects.filter(id__in=user_ids).order_by("id"))
        found_ids = {user.id for user in users}
        missing_ids = [user_id for user_id in user_ids if user_id not in found_ids]
        if missing_ids:
            raise MissingUsers(missing_ids)

        for user in users:
            if user.track_id and not can_admin_track(request.user, user.track_id):
                raise AdminScopeForUserRequired(user.id)
            user.track = target_track
            user.save(update_fields=["track"])

        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)
