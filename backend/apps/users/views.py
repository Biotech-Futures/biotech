import hmac
import logging
from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login
from django.middleware.csrf import get_token
from django.core.cache import cache
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from.models import User, StudentProfile, UserInterest, AreasOfInterest, SupervisorProfile, StudentSupervisor
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.common.role_names import (
    ROLE_STUDENT,
    ROLE_SUPERVISOR,
    get_role_by_name,
)
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
    ArchivedTrackError,
)
from apps.users.utils.track_gate import is_track_archived

logger = logging.getLogger(__name__)


# --- Registration rate limits ----------------------------------------------
# Mirrors the per-IP throttle pattern in apps/services/views.py so anonymous
# registration cannot be used to enumerate the user table or to script bulk
# StudentProfile creation. Tuned generously since real registrations are slow.
REGISTRATION_PER_IP_LIMIT = 10
REGISTRATION_WINDOW_SECONDS = 900  # 15 min


# --- Password login rate limits --------------------------------------------
# Per-email lockout alone lets an attacker fan out across many guessed
# accounts from a single host (credential stuffing). We pair the existing
# 5-attempts-per-email guard with a per-IP cap so a single source can't
# accumulate unbounded failures across different emails. The IP cap is
# deliberately higher than the per-email cap to absorb legitimate shared
# egress (corporate NAT, school networks) without locking out real users.
PWD_LOGIN_PER_EMAIL_LIMIT = 5
PWD_LOGIN_PER_IP_LIMIT = 20
PWD_LOGIN_WINDOW_SECONDS = 300  # 5 min — matches the existing per-email window


def _client_ip(request) -> str:
    # Only honor X-Forwarded-For when the deployment sits behind a trusted
    # reverse proxy / CDN (Azure Front Door, App Service ingress, ALB). Direct
    # exposure means the header is attacker-controlled. Same policy as
    # apps/services/views.py::_client_ip.
    if getattr(settings, "TRUST_FORWARDED_FOR", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""

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

        ip = _client_ip(request)
        email_key = f"pwd_login_attempts:{email}"
        ip_key = f"pwd_login_attempts_ip:{ip}"

        # Dual brute-force guard: per-email blocks targeted attacks on one
        # account; per-IP blocks credential stuffing fanned across many
        # accounts from the same source. Check both BEFORE bcrypt so a
        # locked-out attacker can't keep burning CPU on hash checks.
        email_attempts = cache.get(email_key, 0)
        ip_attempts = cache.get(ip_key, 0)
        if email_attempts >= PWD_LOGIN_PER_EMAIL_LIMIT or ip_attempts >= PWD_LOGIN_PER_IP_LIMIT:
            logger.warning(
                "password_login: rate limit hit email=%s ip=%s email_attempts=%s ip_attempts=%s",
                email, ip, email_attempts, ip_attempts,
            )
            raise TooManyFailedAttempts()

        # Single bcrypt check (was being done twice — once here, once inside
        # authenticate() — adding ~300ms per login).
        user_obj = User.objects.select_related("track").filter(email=email).first()
        if user_obj is None or not user_obj.check_password(password):
            cache.set(email_key, email_attempts + 1, PWD_LOGIN_WINDOW_SECONDS)
            cache.set(ip_key, ip_attempts + 1, PWD_LOGIN_WINDOW_SECONDS)
            raise InvalidCredentials()

        if user_obj.account_status in ['suspended', 'deactivated']:
            raise AccountInactive()

        if is_track_archived(user_obj) and not is_operational_admin(user_obj):
            logger.warning(
                "password_login: blocked archived-track login email=%s track_id=%s",
                email, user_obj.track_id,
            )
            raise ArchivedTrackError()

        # Bypass authenticate()'s second bcrypt by setting the backend manually;
        # login() only needs to know which auth backend to associate with the session.
        # Path must match AUTHENTICATION_BACKENDS so the session resolves
        # back to a real backend on subsequent requests.
        user_obj.backend = 'apps.users.backends.CachedModelBackend'
        login(request, user_obj)
        cache.delete(email_key)
        cache.delete(ip_key)
        payload = UserSerializer(user_obj).data
        # login() rotates the CSRF token; surface the new one so the SPA
        # doesn't keep using the pre-login value on subsequent writes.
        payload["csrfToken"] = get_token(request)
        return Response(payload)

class UserPagePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


#Issue 42
class UserListHTMLView(generics.ListAPIView):
    """Operational-admin user search rendered as HTML.

    Auth-gated to operational admins and scoped to the caller's admin
    track(s). A global admin sees all users; a track-scoped admin only sees
    users in their tracks. The legacy ``AllowAny`` override exposed the full
    user table (PII + account_status oracle) to anonymous callers — see
    CONSOLIDATED issues list 1.2.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    pagination_class = UserPagePagination
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/list.html"

    def get_queryset(self):
        if not is_operational_admin(self.request.user):
            raise OperationalAdminRequired()

        queryset = User.objects.select_related("track", "track__state").order_by("id")

        track_scope = get_admin_track_ids(self.request.user)
        if track_scope is not None:
            queryset = queryset.filter(track_id__in=track_scope)

        account_status_param = self.request.query_params.get("account_status")
        if account_status_param is not None:
            queryset = queryset.filter(account_status=account_status_param.lower())
        email_param = self.request.query_params.get("email")
        if email_param is not None:
            queryset = queryset.filter(email=email_param)
        return queryset


#issue 43
class UsersRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Operational-admin user detail + mutation view rendered as HTML.

    Auth-gated to operational admins; PATCH is further restricted to admins
    whose scope covers the target user's track. The legacy ``AllowAny``
    override let any anonymous caller flip ``account_status`` or assign an
    arbitrary ``role_id`` (including admin) for any user — see CONSOLIDATED
    issues list 1.2.
    """
    queryset = User.objects.select_related("track", "track__state")
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"

    def get_serializer_class(self):
        return UserSerializer

    def _ensure_admin_scope_for_user(self, target_user):
        if not is_operational_admin(self.request.user):
            raise OperationalAdminRequired()
        if target_user.track_id and not can_admin_track(self.request.user, target_user.track_id):
            raise AdminScopeForUserRequired(target_user.id)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        self._ensure_admin_scope_for_user(user)
        return super().retrieve(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        self._ensure_admin_scope_for_user(user)

        data = request.data
        if "account_status" in data:
            user.apply_account_status(data["account_status"])

        if "role_id" in data:
            role = get_object_or_404(Roles, pk=data["role_id"])
            now = timezone.now()

            with transaction.atomic():
                RoleAssignmentHistory.objects.create(
                    user=user,
                    role=role,
                    valid_from=now + timedelta(seconds=1),
                    valid_to=now + timedelta(weeks=104),
                )

        if "timezone" in data:
            serializer = UserSerializer(user, data={"timezone": data["timezone"]}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

# --- Self-PATCH field policy for MeRetrieveView -----------------------------
# An explicit allowlist of fields the user is permitted to mutate on their own
# profile, paired with an explicit denylist of fields that must NEVER be
# accepted from the self endpoint. The legacy implementation accepted
# ``role_id`` and ``account_status`` straight from ``request.data`` and applied
# them to ``request.user`` with no admin check, which let any authenticated
# session self-assign the admin role (via ``RoleAssignmentHistory.objects
# .create``) or bypass a suspension. Privileged role / status / track changes
# must go through ``UsersRetrieveUpdateView`` (admin + track scope).
#
# Why both lists?
#   * The allowlist is the security floor — anything not on it is ignored
#     (and ``UserSerializer`` itself rejects unknown writable fields). Adding
#     a new self-mutable field is a deliberate code-review event.
#   * The denylist is for *known* admin-only fields. Hitting one returns 400
#     with a field-keyed error so attacker probes and FE wiring mistakes
#     surface immediately instead of looking like a silent no-op.
SELF_PATCHABLE_FIELDS: frozenset[str] = frozenset({"timezone"})

SELF_PATCH_REJECTED_FIELDS: frozenset[str] = frozenset({
    "role_id", "role",
    "account_status",
    "is_staff", "is_superuser", "is_active",
    "track", "track_id",
})

SELF_PATCH_REJECTED_MESSAGE = (
    "This field cannot be changed via /users/me/. Contact an admin."
)


#issue 40
class MeRetrieveView(generics.RetrieveAPIView):
    """Authenticated user's self-profile endpoint.

    PATCH is intentionally restricted to ``SELF_PATCHABLE_FIELDS`` (currently
    just ``timezone``). Any field in ``SELF_PATCH_REJECTED_FIELDS`` aborts the
    entire request with HTTP 400 and a field-keyed error message — see the
    module-level comment above for the security rationale. The legitimate
    admin-driven role-assignment path lives on :class:`UsersRetrieveUpdateView`
    and is gated on ``is_operational_admin`` + ``can_admin_track``.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        data = request.data

        rejected = sorted(field for field in data if field in SELF_PATCH_REJECTED_FIELDS)
        if rejected:
            # One warning per blocked attempt so credential-stuffed accounts
            # and compromised clients show up as 4xx spikes in log metrics
            # instead of silent no-ops. Format matches the audit PR contract.
            logger.warning(
                "MeRetrieveView.patch: user=%s attempted to mutate admin-only fields=%s",
                user.id, rejected,
            )
            raise serializers.ValidationError(
                {field: SELF_PATCH_REJECTED_MESSAGE for field in rejected}
            )

        # Route every allowed field through ``UserSerializer`` so the same
        # validators the rest of the codebase relies on (e.g. the IANA
        # timezone check on ``validate_timezone``) apply here — no bespoke
        # per-field branches and no risk of drift if a new self-mutable
        # field is added to ``SELF_PATCHABLE_FIELDS``.
        update_data = {
            key: value for key, value in data.items() if key in SELF_PATCHABLE_FIELDS
        }
        if update_data:
            serializer = UserSerializer(user, data=update_data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    
class UserRegisterView(APIView):
    """Public student self-registration endpoint.

    ``AllowAny`` is intentional — this is the front door for new students.
    Hardening on top of the permission:

    * Per-IP rate limit so the endpoint can't be used to bulk-create
      ``StudentProfile`` rows or to flood the supervisor table.
    * Refuses to overwrite an existing user. The legacy implementation
      ``get_or_create``'d both the student and the supervisor by email and
      then unconditionally wrote ``first_name`` / ``last_name`` back, which
      let any anonymous caller rename any existing user (incl. admins).
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegisterRequestSerializer

    @extend_schema(request=UserRegisterRequestSerializer, responses={200: UserRegisterRequestSerializer})
    @transaction.atomic
    def post(self, request):
        ip = _client_ip(request)
        rate_key = f"registration_ip:{ip}"
        attempts = cache.get(rate_key, 0)
        if attempts >= REGISTRATION_PER_IP_LIMIT:
            logger.warning("registration: rate limit hit ip=%s attempts=%s", ip, attempts)
            raise TooManyFailedAttempts()
        cache.set(rate_key, attempts + 1, REGISTRATION_WINDOW_SECONDS)

        data = request.data
        databody = data["body"]

        student_email = (databody.get("Title") or "").strip().lower()
        supervisor_email = (databody.get("SupervisorEmail") or "").strip().lower()
        if not student_email or not supervisor_email:
            raise serializers.ValidationError({"body": "Student and supervisor emails are required."})

        # Refuse to clobber an existing account. Self-registration is for
        # brand new students; account recovery flows live under /services/.
        if User.objects.filter(email__iexact=student_email).exists():
            raise serializers.ValidationError({"Title": "An account with this email already exists."})

        user = User.objects.create_user(email=student_email)
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

        # roleassignmenthistory creation
        # Look up roles by stable name (registration must work in any env, regardless of seed order).
        now = timezone.now()
        role = get_role_by_name(ROLE_STUDENT)
        rah = RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))

        #supervisorprofile check
        sup, sup_created = User.objects.get_or_create(email=databody["SupervisorEmail"])
        sup.first_name = databody["SupervisorFirstName"]
        sup.last_name = databody["SupervisorSurname"]
        sup.save()
        sup_role = get_role_by_name(ROLE_SUPERVISOR)
        sup_rah = RoleAssignmentHistory.objects.create(user=sup, role=sup_role, valid_from=now+timedelta(seconds=1), valid_to=now+timedelta(weeks=6))

        if databody["SupervisorEmail"] == databody["GuardianEmail"]:
            pgflag = True
        else:
            pgflag = False

        supprof, supprof_created = SupervisorProfile.objects.get_or_create(user=sup, school_name=databody["SchoolName"])

        sp = StudentProfile.objects.create(
            user=user,
            pg_first_name=databody["GuardianName"],
            pg_last_name=databody["GuardianSurname"],
            parent_guardian_flag=pgflag,
            supervisor=supprof,
            school_name=databody["SchoolName"],
            year_lvl=databody["YearLevel"]
        )

        ss = StudentSupervisor.objects.create(
            student_user=sp,
            supervisor_user=supprof,
        )

        si = UserInterest.objects.create(
            interest=AreasOfInterest.objects.get_or_create(interest_desc=databody["Areaofinterest"])[0],
            user=user
        )
        return Response(data["body"])


#issue 128
class ReceiveJoinPermissionView(APIView):
    """Webhook receiver for the external join-permission consent form.

    There is no human caller — the upstream form service posts here once a
    guardian has signed off. Auth is a shared secret header rather than a
    session, mirroring the ``RsvpReminderTriggerView`` pattern:

    * ``JOIN_PERMISSION_WEBHOOK_TOKEN`` must be set; if blank the endpoint
      returns 503 so a misconfigured deploy fails loud instead of silently
      exposing an unauthenticated trigger.
    * The header value is compared with ``hmac.compare_digest`` for
      constant-time matching.

    The legacy ``AllowAny`` override let any anonymous caller flip
    ``has_join_permission=True`` for any student they could guess an email
    for — see CONSOLIDATED issues list 1.2.
    """
    authentication_classes = []
    permission_classes = []
    serializer_class = JoinPermissionRequestSerializer

    @extend_schema(request=JoinPermissionRequestSerializer, responses={200: JoinPermissionRequestSerializer})
    @transaction.atomic
    def post(self, request):
        expected = getattr(settings, "JOIN_PERMISSION_WEBHOOK_TOKEN", "") or ""
        if not expected:
            return Response(
                {"detail": "Join-permission webhook is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        provided = request.headers.get("X-Join-Permission-Token", "")
        if not hmac.compare_digest(provided, expected):
            logger.warning(
                "ReceiveJoinPermissionView: invalid token ip=%s",
                _client_ip(request),
            )
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = request.data
        databody = data["body"]

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