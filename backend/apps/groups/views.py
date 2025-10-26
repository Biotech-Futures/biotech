from typing import List, Tuple
from apps.groups.services.get_group_name import generate_group_name
from apps.users.services.registration import register_user, UserAlreadyExists
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from .serializers import CountrySerializer, GroupMemberSerializer, TrackSerializer, GroupSerializer, AddGroupMembersSerializer
from .services.get_track import (
    get_supported_track,
    TrackResolutionError,
    InvalidInputError,
    CountryNotFoundError,
    StateNotFoundError,
    TrackNotConfiguredError,
)
from .models import Groups, Countries, GroupMembers, Tracks, CountryStates
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, filters, status
from rest_framework import serializers as drf_serializers
from django.db.models import Exists, OuterRef
from django.db.models.functions import Now
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
import logging
import re
logger = logging.getLogger(__name__)

# API schema annotations
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    inline_serializer,
)
from apps.resources.models import RoleAssignmentHistory 


# Create your views here.

User = get_user_model()


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Countries.objects.all()
    serializer_class = CountrySerializer

    def get_permissions(self):
        # allow read for anybody and only write for admin
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminUser()]  # to check if the user has .is_staff flag


class GroupMemberViewSet(viewsets.ModelViewSet):
    queryset = GroupMembers.objects.all()
    serializer_class = GroupMemberSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "by_group"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='by-group/(?P<group_id>[^/.]+)')
    def by_group(self, request, group_id=None):
        """Custom action to get members by group ID"""
        members = self.queryset.filter(group_id=group_id)
        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)

    # TODO: expand by addung endpoints to implement logic of adding and removing members


class TrackViewSet(viewsets.ModelViewSet):
    queryset = Tracks.objects.all()
    serializer_class = TrackSerializer
    http_method_names = ['get', 'post', 'put', 'patch']  # disable delete
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['track_name', 'id']
    search_fields = ['track_name']

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class GroupPaginator(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    pagination_class = GroupPaginator
    # we will look up with groups/R_12skjXJde/ instead of groups/12/
    lookup_field = "group_number"
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["track"]  # now you can do /groups/?track=3
    ordering_fields = ['group_name', 'creation_datetime']
    search_fields = ['group_name', 'group_number', 'track__track_name']
    ordering = ["-creation_datetime"]

    # TODO: test search fields e.g. group_name, group_number, track__track_name, pagination e.g. ?page=2,
    # GET /groups/?page=2 (pagination)
    # GET /groups/?search=alpha (search)
    # GET /groups/?track=5 (filter by track)
    # GET /groups/?track=5&search=alpha&ordering=group_name (all together)

    # by default, don't include the deleted flags. only show if include_deleted in query param
    def get_queryset(self):
        raw = (self.request.query_params.get(
            'include_deleted') or '').lower().strip()
        if raw == 'true' and self.request.user.is_staff:
            return Groups.objects.all()
        return Groups.objects.filter(deleted_flag=False)

    # read for authenticated and write for authorised
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    # DRF will use lookup_field (group_number) for retrieve/update/destroy

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.deleted_flag:
            # means group is alr deleted but no errors
            return Response(status=status.HTTP_204_NO_CONTENT)
        group.deleted_flag = True
        group.deleted_datetime = timezone.now()
        group.save(update_fields=['deleted_flag', 'deleted_datetime'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def restore(self, request, *args, **kwargs):
        group = self.get_object()
        if not group.deleted_flag:
            return Response({"detail": f"Group {group.group_name} is already active."}, status=status.HTTP_200_OK)

        new_name = (request.data.get("new_group_name") or group.group_name)
        if not new_name or not str(new_name).strip():
            # it is blank
            return Response({"new_group_name": ["Name cannot be blank"]}, status=status.HTTP_400_BAD_REQUEST)
        new_name = new_name.strip()
        renamed = new_name != group.group_name

        clash = Groups.objects.filter(
            track=group.track,
            group_name=new_name,
            cohort_year=group.cohort_year,
            deleted_flag=False
        ).exclude(pk=group.pk).exists()

        if clash:
            return Response({"error": f"Another group in {group.cohort_year}: {group.track} has been made with this name."}, status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            group.group_name = new_name
            group.deleted_flag = False
            group.deleted_datetime = None
            group.save(update_fields=['group_name',
                       'deleted_flag', 'deleted_datetime'])
        data = self.get_serializer(group).data
        return Response({"restored": True, "renamed": renamed, "group": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def register_student(self, request, *args, **kwargs):
        '''
        custom endpoint to handle multiple single group member additions
        ensures the group via group_number exists, if not create
        if the student is already a member, then no error - idempotency
        lenient: it will create what it can and then report any per-step outcomes
        '''

        raw = request.data.get('body') or request.data
        group_number = raw.get('GroupNumber')
        student_email = raw.get('Title')
        student_first_name = raw.get('FirstName')
        student_surname = raw.get('Surname')
        pg_first_name = raw.get('GuardianName')
        pg_last_name = raw.get('GuardianSurname')
        guardian_email = raw.get('GuardianEmail')
        supervisor_first_name = raw.get("SupervisorFirstName")
        supervisor_last_name = raw.get("SupervisorSurname")
        supervisor_email = raw.get('SupervisorEmail')
        interest = raw.get("Areaofinterest")
        school_name = raw.get('SchoolName')
        year_level = raw.get('YearLevel')
        # TODO: maybe check that there is a group name field, or set it to this by default
        group_name = group_number
        submission_created = raw.get('Created')
        cohort_year = timezone.now().year  # default to receive date year
        if submission_created and isinstance(submission_created, str):
            try:
                cohort_year = int(
                    (submission_created.split('-')[0] or '').strip())
            except Exception:
                cohort_year = timezone.now().year

        country_name = raw.get('Country')
        region = raw.get('Region')

        # conduct basic validation - returning 400
        errors = {}
        if not group_number:
            errors["group_number"] = "Group Number not provided."
        if not student_email:
            errors["student_email"] = "Student Email not provided"
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # resolve track from country and region via helper
        try:
            track = get_supported_track(country_name, region)
        except InvalidInputError as e:
            return Response({"Track": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        except CountryNotFoundError as e:
            return Response({"Country": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        except StateNotFoundError as e:
            return Response({"State": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        except TrackNotConfiguredError as e:
            return Response({"Track": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        except TrackResolutionError as e:
            # generic fallback
            return Response({"Track": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        if not track:
            return Response({"Track": ["Unable to resolve Track."]}, status=status.HTTP_400_BAD_REQUEST)

        # ensure/restore group by group number

        group_created = False
        with transaction.atomic():
            group_name = generate_group_name(track, cohort_year)
            group, created = Groups.objects.get_or_create(
                group_number=group_number,
                defaults={  # specifies values for fields that are only set when a new object is created
                    "group_name": group_name,
                    "track": track,
                    "cohort_year": cohort_year
                },
            )
            group_created = created  # bool

            if not created and group.deleted_flag:
                # auto restore, if no active-name clash
                clash = Groups.objects.filter(
                    track=group.track,
                    cohort_year=group.cohort_year,
                    group_name=group.group_name,
                    deleted_flag=False
                ).exclude(pk=group.pk).exists()
                if clash:
                    return Response(
                        {"detail": f"Attempted to auto-restore existing group for {group.cohort_year}: {group.track} with name {group.group_name} however one already exists. Rename via /restore."},
                        status=status.HTTP_409_CONFLICT
                    )
                group.deleted_flag = False
                group.deleted_datetime = None
                group.save(update_fields=['deleted_flag', 'deleted_datetime'])

        # resolve/create student user by email
        # first, get the user object by filtering through email, using first()
        # TODO: create a shared service function in Users/services/ to get or create a user?
        user = None
        user_created = None
        user_creation_kwargs = {
            "email": student_email,
            "first_name": student_first_name,
            "last_name": student_surname,
            "country_name": country_name,
            "region_name": region,
            "pg_first_name": pg_first_name,
            "pg_last_name": pg_last_name,
            "supervisor_email": supervisor_email,
            "supervisor_first_name": raw.get("SupervisorFirstName"),
            "supervisor_last_name": raw.get("SupervisorSurname"),
            "interest": interest,
            "year_level": year_level,
            "school_name": school_name
        }
        try:
            user, user_profile = register_user(user_creation_kwargs, "student")
            user_created = True
        except UserAlreadyExists:
            logger.info("User already exists: %s, continuing", student_email)
            user = User.objects.filter(email__iexact=student_email).first()
            user_created = False
            if not user:
                return Response({"Student": [f"User '{student_email}' exists but could not be retrieved."]},
                                status=status.HTTP_400_BAD_REQUEST)

        # then, add membership, initialise variable to track adding
        member_created = False
        try:
            membership, m_created = GroupMembers.objects.get_or_create(
                group=group, user=user)
            member_created = m_created
        except Exception as e:
            return Response(
                {
                    "group_created": group_created,
                    "user_created": user_created,
                    "member_added": False,  # we run into this error here if member doesn't get added
                    "member_error": str(e),
                    "group": GroupSerializer(group).data
                },
                status=status.HTTP_200_OK
            )

        # this is fully successful
        resp = {
            "group_created": group_created,
            "user_created": user_created,
            "member_added": member_created,
            "group": GroupSerializer(group).data,
            "student": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        }
        return Response(resp, status=status.HTTP_201_CREATED if group_created else status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='members', permission_classes=[IsAdminUser])
    def members(self, request, *args, **kwargs):
        """
        Add users as members to the specified group (by group_number).

        Request route:
          POST /groups/groups/{group_number}/members/

        Input (JSON):
          - user_ids: [int, ...]            optional, list of user primary keys
          - user_emails: [str, ...]         optional, list of user emails (case-insensitive)
          - ignore_existing: bool           optional, currently unused (reserved), defaults to true

        Constraints:
          - At least one of user_ids or user_emails must be provided.
          - The target group must be active (not deleted).

        Response (200 OK):
          {
            "summary": {
              "requested": N,
              "added": X,
              "already_member": Y,
              "not_found": Z,
              "errors": E
            },
            "results": [
              {"identifier": 12, "type": "id", "status": "added" | "already_member" | "not_found" | "error", "error": "..."?},
              {"identifier": "user@example.com", "type": "email", "status": "..."}
            ],
            "group": { ...GroupSerializer payload... }
          }

        Notes:
          - Operation is idempotent due to the unique(group, user) constraint.
          - This endpoint does not create users from emails; unknown identifiers are reported as not_found.
        """

        def validate_ids(payload: List) -> Tuple[bool, str]:
            if not payload:
                return False, "No users to add."
            for entry in payload:
                try:
                    int(entry)
                except (TypeError, ValueError):
                    return False, "Non-user ID found in users-to-add list."
            return True, "Success"

        def validate_emails(payload: List[str]) -> Tuple[bool, str]:
            if not payload:
                return False, "No users to add."
            regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            for entry in payload:
                if re.fullmatch(regex, str(entry)) is None:
                    return False, "Invalid email found in users-to-add list."
            return True, "Success"

        group = self.get_object()
        if group.deleted_flag is True:
            return Response({"Group": [f"Group {group.group_number} - {group.group_name} is currently inactive."]}, status=status.HTTP_409_CONFLICT)

        # validate through serializer
        raw = request.data.get('body') or request.data
        serializer = AddGroupMembersSerializer(data=raw)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data.get("user_ids") or []
        user_emails = serializer.validated_data.get("user_emails") or []

        # normalise input, removing duplicate if duplicate are found
        user_ids = [int(x) for x in user_ids] if user_ids else []
        user_ids = list(dict.fromkeys(user_ids))
        user_emails = [str(x).strip() for x in user_emails] if user_emails else []
        user_emails = list(dict.fromkeys(user_emails))

        ok_ids, msg_ids = validate_ids(user_ids) if user_ids else (True, "")
        ok_emails, msg_emails = validate_emails(user_emails) if user_emails else (True, "")
        if not ok_ids:
            return Response({"Members": [f"Malformed user_ids list: {msg_ids}"]}, status=status.HTTP_400_BAD_REQUEST)
        if not ok_emails:
            return Response({"Members": [f"Malformed user_emails list: {msg_emails}"]}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        added = 0
        already = 0
        not_found = 0
        errors = 0

        # resolve id of user
        if user_ids:
            existing_users_by_id = {u.id: u for u in User.objects.filter(id__in=user_ids)}
            for uid in user_ids:
                user = existing_users_by_id.get(uid)
                if not user:
                    not_found += 1
                    results.append({"identifier": uid, "type": "id", "status": "not_found"})
                    continue
                try:
                    _, created = GroupMembers.objects.get_or_create(group=group, user=user)
                    if created:
                        added += 1
                        results.append({"identifier": uid, "type": "id", "status": "added"})
                    else:
                        already += 1
                        results.append({"identifier": uid, "type": "id", "status": "already_member"})
                except Exception as e:
                    errors += 1
                    results.append({"identifier": uid, "type": "id", "status": "error", "error": str(e)})

        # get user thru email
        if user_emails:
            for email in user_emails:
                try:
                    user = User.objects.filter(email__iexact=email).first()
                except Exception:
                    user = None
                if not user:
                    not_found += 1
                    results.append({"identifier": email, "type": "email", "status": "not_found"})
                    continue
                try:
                    _, created = GroupMembers.objects.get_or_create(group=group, user=user)
                    if created:
                        added += 1
                        results.append({"identifier": email, "type": "email", "status": "added"})
                    else:
                        already += 1
                        results.append({"identifier": email, "type": "email", "status": "already_member"})
                except Exception as e:
                    errors += 1
                    results.append({"identifier": email, "type": "email", "status": "error", "error": str(e)})

        summary = {
            "requested": len(user_ids) + len(user_emails),
            "added": added,
            "already_member": already,
            "not_found": not_found,
            "errors": errors,
        }

        return Response({
            "summary": summary,
            "results": results,
            "group": GroupSerializer(group).data
        }, status=status.HTTP_200_OK)
    

    # build an endpoint GET /groups/groups/without-mentor
    # returns: a paginated list of active groups that have no member whose active role is Mentor
    # data per group includes
    #   group_number, group_name, cohort_year
    #   track_id, track_name, region
    #   students
    #     school, area of interest
    #   member_count    

    @extend_schema(
        summary="List groups without an active mentor",
        description=(
            "Returns a paginated list of active groups that have no member whose current active role is Mentor.\n\n"
            "Mentor presence is defined via RoleAssignmentHistory: valid_to is null and valid_from <= now for role 'Mentor'.\n"
            "Supports filtering by track (id or name), cohort_year, and region (state name)."
        ),
        parameters=[
            OpenApiParameter(name="track", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                             description="Track id (numeric) or track name (string)"),
            OpenApiParameter(name="cohort_year", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                             description="Cohort year (e.g., 2025)"),
            OpenApiParameter(name="region", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                             description="Region (state name), case-insensitive"),
            OpenApiParameter(name="page", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                             description="Page number (pagination)"),
            OpenApiParameter(name="page_size", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                             description="Results per page (pagination)"),
        ],
        responses=inline_serializer(
            name="GroupsWithoutMentorPage",
            fields={
                "count": drf_serializers.IntegerField(),
                "next": drf_serializers.URLField(allow_null=True, required=False),
                "previous": drf_serializers.URLField(allow_null=True, required=False),
                "results": drf_serializers.ListSerializer(
                    child=inline_serializer(
                        name="GroupWithoutMentorItem",
                        fields={
                            "group_number": drf_serializers.CharField(),
                            "group_name": drf_serializers.CharField(),
                            "cohort_year": drf_serializers.IntegerField(),
                            "track": inline_serializer(
                                name="TrackMini",
                                fields={
                                    "id": drf_serializers.IntegerField(),
                                    "name": drf_serializers.CharField(),
                                }
                            ),
                            "region": drf_serializers.CharField(allow_null=True, required=False),
                            "member_count": drf_serializers.IntegerField(),
                            "students": drf_serializers.ListSerializer(
                                child=inline_serializer(
                                    name="StudentMini",
                                    fields={
                                        "school": drf_serializers.CharField(),
                                        "interest": drf_serializers.CharField(allow_null=True, required=False),
                                    }
                                )
                            ),
                        }
                    )
                ),
            }
        ),
        tags=["Groups"],
    )
    @action(detail=False, methods=['get'], url_path='without-mentor', permission_classes=[IsAdminUser])
    def without_mentor(self, request, *args, **kwargs):
        """
    Returns a paginated list of active groups that have no member whose current active role is Mentor.

        Route:
          GET /groups/groups/without-mentor/

        Response (paginated):
          {
            "count": N,
            "next": url|null,
            "previous": url|null,
            "results": [
              {
                "group_number": str,
                "group_name": str,
                "cohort_year": int,
                "track": {"id": int, "name": str},
                "region": str,  # state name from the group's track
                "member_count": int,
                "students": [
                  {"school": str, "interest": str|null},
                  ...
                ]
              },
              ...
            ]
          }
        """

        # we make our queryset only groups who are active, and we select related information so as to not do extra queries.
        # we get the track of the group, the state which comes from track, and the country which comes from the state/
        qs = Groups.objects.filter(deleted_flag=False).select_related(
            "track", "track__state", "track__state__country"
        )

        # annotate: whether group has at least one member whose ACTIVE role is Mentor

        active_mentor_exists = RoleAssignmentHistory.objects.filter(
            user__groupmembers__group=OuterRef("pk"),
            role__role_name__iexact="mentor",
            valid_to__isnull=True,
            valid_from__lte=Now(),
        )
        qs = qs.annotate(
            has_mentor=Exists(active_mentor_exists),
        ).filter(has_mentor=False)

        # optional filters (track, cohort_year, region)
        track_param = request.query_params.get("track")
        if track_param:
            if str(track_param).isdigit():
                # try to search for track id first
                qs = qs.filter(track_id=int(track_param))
            else:
                # then try for track name
                qs = qs.filter(track__track_name__iexact=str(track_param))
        cohort_param = request.query_params.get("cohort_year")
        if cohort_param and str(cohort_param).isdigit():
            qs = qs.filter(cohort_year=int(cohort_param))
        region_param = request.query_params.get("region")
        if region_param:
            qs = qs.filter(track__state__state_name__iexact=str(region_param))

        # paginate
        page = self.paginate_queryset(qs)
        if page is None:
            page_items = list(qs)
        else:
            page_items = list(page)

        # prefetch members + related student profile and interest for only the paginated groups
        group_ids = [g.id for g in page_items]
        members_qs = (
            GroupMembers.objects
            .filter(group_id__in=group_ids)
            .select_related("user", "user__studentprofile", "user__studentprofile__interest")
        )

        members_by_group = {}
        for gm in members_qs:
            members_by_group.setdefault(gm.group_id, []).append(gm)

        def serialize_group(g: Groups):
            # students = only those members whose user has a StudentProfile
            students = []
            for gm in members_by_group.get(g.id, []) or []:
                sp = getattr(gm.user, "studentprofile", None)
                if sp is None:
                    continue
                students.append({
                    "school": sp.school_name,
                    "interest": (sp.interest.interest_desc if sp.interest else None),
                })

            return {
                "group_number": g.group_number,
                "group_name": g.group_name,
                "cohort_year": g.cohort_year,
                "track": {"id": g.track_id, "name": g.track.track_name},
                "region": g.track.state.state_name if g.track and g.track.state else None,
                "member_count": len(members_by_group.get(g.id, [])),
                "students": students,
            }

        data = [serialize_group(g) for g in page_items]

        if page is None:
            # not paginated (unlikely because paginator is set), mimic standard DRF response
            return Response({"count": len(data), "next": None, "previous": None, "results": data}, status=status.HTTP_200_OK)
        return self.get_paginated_response(data)
        
