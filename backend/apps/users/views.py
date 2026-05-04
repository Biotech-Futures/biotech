from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from.models import User, StudentProfile, UserInterest, AreasOfInterest, SupervisorProfile, StudentSupervisor
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Countries, CountryStates, Groups
from apps.events.models import Events
from apps.matching_runtime.models import MatchRecommendation
from .serializers import (
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AdminOperationsSummarySerializer,
    BulkUserStatusSerializer,
    BulkUserTrackSerializer,
    JoinPermissionRequestSerializer,
    MeProfileUpdateSerializer,
    UserRegisterRequestSerializer,
    UserSerializer,
    UserStatusPatchSerializer,
)
from .utils.admin_scope import can_admin_track, get_admin_track_ids, is_operational_admin


def _apply_account_status(user, account_status):
    # Centralize account-status side effects so single-user and bulk admin flows behave the same.
    now = timezone.now()
    user.account_status = account_status
    update_fields = {"account_status", "is_active"}
    if user.account_status == User.AccountStatus.ACTIVE and user.activated_at is None:
        user.activated_at = now
        update_fields.add("activated_at")
    if user.account_status == User.AccountStatus.INVITED and user.invited_at is None:
        user.invited_at = now
        update_fields.add("invited_at")
    user.save(update_fields=list(update_fields))


def _assign_role(user, role_id, *, valid_weeks):
    # Role assignment is reused by both self-service and admin patch flows.
    role = get_object_or_404(Roles, pk=role_id)
    now = timezone.now()
    RoleAssignmentHistory.objects.create(
        user=user,
        role=role,
        valid_from=now + timedelta(seconds=1),
        valid_to=now + timedelta(weeks=valid_weeks),
    )


class IsOperationalAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_operational_admin(request.user)

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
        
        # Clean Code: Guard against Brute-Force
        cache_key = f"pwd_login_attempts:{email}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            return Response({"error": "Too many failed attempts. Try again in 5 minutes."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
        user_obj = User.objects.filter(email=email).first()
        if user_obj and user_obj.check_password(password):
            if user_obj.account_status in ['suspended', 'deactivated']:
                return Response({"error": "Account is inactive."}, status=status.HTTP_403_FORBIDDEN)
            
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user) # Initiates Django Session
            cache.delete(cache_key)
            return Response(UserSerializer(user).data)
        else:
            cache.set(cache_key, attempts + 1, 300) # 5 min lockout
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

class UserPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminUserListView(generics.ListAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsOperationalAdminPermission]
    renderer_classes = [JSONRenderer]
    pagination_class = UserPagePagination

    def get_queryset(self):
        # `api/v1/users/` is now the JSON-first admin/SPA surface; keep filtering predictable
        # so the frontend and future external clients can rely on one contract.
        queryset = User.objects.select_related("track", "track__state").order_by("id")
        track_scope = get_admin_track_ids(self.request.user)
        if track_scope is not None:
            queryset = queryset.filter(Q(track_id__in=track_scope) | Q(track__isnull=True))

        account_status = self.request.query_params.get("account_status")
        if account_status:
            queryset = queryset.filter(account_status=account_status.lower())

        email = self.request.query_params.get("email")
        if email:
            queryset = queryset.filter(email__iexact=email.strip())

        search = self.request.query_params.get("q")
        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        track_id = self.request.query_params.get("track_id")
        if track_id:
            queryset = queryset.filter(track_id=track_id)

        ordering = self.request.query_params.get("ordering", "id")
        allowed_ordering = {
            "id",
            "-id",
            "email",
            "-email",
            "first_name",
            "-first_name",
            "last_name",
            "-last_name",
            "account_status",
            "-account_status",
            "invited_at",
            "-invited_at",
            "activated_at",
            "-activated_at",
        }
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering, "id")

        return queryset

class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsOperationalAdminPermission]
    renderer_classes = [JSONRenderer]

    def get_queryset(self):
        queryset = User.objects.select_related("track", "track__state").order_by("id")
        track_scope = get_admin_track_ids(self.request.user)
        if track_scope is None:
            return queryset
        return queryset.filter(Q(track_id__in=track_scope) | Q(track__isnull=True))

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        # Admin detail PATCH shares the same contract fields as the list surface so the UI
        # does not need a separate response-shape adapter after writes.
        user = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if user.track_id and not can_admin_track(request.user, user.track_id):
            return Response(
                {"detail": f"You do not have admin scope for user {user.id}."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = serializer.validated_data
        target_track = data.get("track")
        if target_track and not can_admin_track(request.user, target_track):
            return Response(
                {"detail": "You do not have admin scope for the target track."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if "account_status" in data:
            _apply_account_status(user, data["account_status"])

        if target_track is not None:
            user.track = target_track
            user.save(update_fields=["track"])

        if "role_id" in data:
            _assign_role(user, data["role_id"], valid_weeks=104)

        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)
    
#issue 40
class MeRetrieveView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_object(self):
        obj = self.request.user
        return obj
    
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = MeProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []
        # Self-service profile updates are intentionally limited to user-editable identity and
        # preference fields; account status and role changes remain admin-only operations.
        for field_name in ["first_name", "last_name", "contact_method", "availability"]:
            if field_name in data:
                setattr(user, field_name, data[field_name])
                update_fields.append(field_name)

        if update_fields:
            user.save(update_fields=update_fields)

        if "interests" in data:
            UserInterest.objects.filter(user=user).delete()
            for interest_desc in data["interests"]:
                interest, _ = AreasOfInterest.objects.get_or_create(interest_desc=interest_desc)
                UserInterest.objects.create(user=user, interest=interest)

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
            return Response({"detail": "Operational admin access is required."}, status=status.HTTP_403_FORBIDDEN)

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
            return Response({"detail": "Operational admin access is required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BulkUserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data["user_ids"]
        users = list(User.objects.filter(id__in=user_ids).order_by("id"))
        found_ids = {user.id for user in users}
        missing_ids = [user_id for user_id in user_ids if user_id not in found_ids]
        if missing_ids:
            return Response({"missing_user_ids": missing_ids}, status=status.HTTP_400_BAD_REQUEST)

        for user in users:
            if user.track_id and not can_admin_track(request.user, user.track_id):
                return Response(
                    {"detail": f"You do not have admin scope for user {user.id}."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            _apply_account_status(user, serializer.validated_data["account_status"])

        return Response(AdminUserSerializer(users, many=True).data, status=status.HTTP_200_OK)


class BulkUserTrackAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    @extend_schema(request=BulkUserTrackSerializer, responses={200: UserSerializer(many=True)})
    @transaction.atomic
    def post(self, request):
        if not is_operational_admin(request.user):
            return Response({"detail": "Operational admin access is required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BulkUserTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_track = serializer.validated_data["track"]
        if not can_admin_track(request.user, target_track):
            return Response({"detail": "You do not have admin scope for the target track."}, status=status.HTTP_403_FORBIDDEN)

        user_ids = serializer.validated_data["user_ids"]
        users = list(User.objects.filter(id__in=user_ids).order_by("id"))
        found_ids = {user.id for user in users}
        missing_ids = [user_id for user_id in user_ids if user_id not in found_ids]
        if missing_ids:
            return Response({"missing_user_ids": missing_ids}, status=status.HTTP_400_BAD_REQUEST)

        for user in users:
            if user.track_id and not can_admin_track(request.user, user.track_id):
                return Response(
                    {"detail": f"You do not have admin scope for user {user.id}."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            user.track = target_track
            user.save(update_fields=["track"])

        return Response(AdminUserSerializer(users, many=True).data, status=status.HTTP_200_OK)
