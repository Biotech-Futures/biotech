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
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
import logging
import re
logger = logging.getLogger(__name__)


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
        

            # "GroupNumber": "R_49n3r8XlHkOmYKJ_1",
            # "Title": "student.@education.com",
            # "FirstName": "John",
            # "Surname": "Doe",
            # "GuardianName": "Jane",
            # "GuardianSurname": "Smith",
            # "GuardianEmail": "jane.smith@outlook.com",
            # "SchoolName": "University of Sydney",
            # "YearLevel": "10",
            # "Areaofinterest": "Space & Astrobiology",
            # "SupervisorEmail": "super@visor.com",
            # "Country": "Australia",
            # "Region": "NSW",
            # "Created": "2025-09-17T09:05:22Z"

            # body": {
            #         "@odata.etag": "\"1\"",
            #         "ItemInternalId": "615",
            #         "ID": 615,
            #         "Title": "john.smith@education.com",
            #         "FirstName": "John",
            #         "Surname": "Smith",
            #         "GuardianName": "Jane",
            #         "GuardianSurname": "Smith",
            #         "GuardianEmail": "jane.smith@outlook.com",
            #         "SchoolName": "School ABC",
            #         "YearLevel": "9",
            #         "Areaofinterest": "Space & Astrobiology",
            #         "GroupNumber": "R_49n3r8XlHkOmYKJ_1",
            #         "SupervisorFirstName": "William",
            #         "SupervisorSurname": "Nixon",
            #         "SupervisorEmail": "william.nixon@sydney.edu.au",
            #         "Registeredby": "Supervisor",
            #         "UniqueID0": "78f4e327-a3fc-4a4c-8608-69ad94ac3291",
            #         "Country": "Australia",
            #         "Region": "NSW",
            #         "GroupingType": "1",
            #         "Modified": "2025-09-17T09:05:22Z",
            #         "Created": "2025-09-17T09:05:22Z",
            #         "Author": {
            #             "@odata.type": "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser",
            #             "Claims": "i:0#.f|membership|william.nixon@sydney.edu.au",
            #             "DisplayName": "William Nixon",
            #             "Email": "william.nixon@sydney.edu.au",
            #             "Picture": "https://unisyd.sharepoint.com/teams/az-BTFtr-358/_layouts/15/UserPhoto.aspx?Size=L&AccountName=william.nixon@sydney.edu.au",
            #             "Department": "School of Biomedical Engineering",
            #             "JobTitle": "Administrative Officer"
            #         },
            #         "Author#Claims": "i:0#.f|membership|william.nixon@sydney.edu.au",
            #         "Editor": {
            #             "@odata.type": "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser",
            #             "Claims": "i:0#.f|membership|william.nixon@sydney.edu.au",
            #             "DisplayName": "William Nixon",
            #             "Email": "william.nixon@sydney.edu.au",
            #             "Picture": "https://unisyd.sharepoint.com/teams/az-BTFtr-358/_layouts/15/UserPhoto.aspx?Size=L&AccountName=william.nixon@sydney.edu.au",
            #             "Department": "School of Biomedical Engineering",
            #             "JobTitle": "Administrative Officer"
            #         },
            #         "Editor#Claims": "i:0#.f|membership|william.nixon@sydney.edu.au",
            #         "{Identifier}": "Lists%252f2025%2bParticipants%252f615_.000",
            #         "{IsFolder}": false,
            #         "{Thumbnail}": {
            #             "Large": null,
            #             "Medium": null,
            #             "Small": null
            #         },
            #         "{Link}": "https://unisyd.sharepoint.com/teams/az-BTFtr-358/_layouts/15/listform.aspx?PageType=4&ListId=54ede385%2D4c69%2D4ec2%2Da2d3%2D2bf4929d6b16&ID=615&ContentTypeID=0x0100D97499FA4F06944DB3F296DB8C896C550039647431C4705A409B62E2883347CFBE",
            #         "{Name}": "john.smith@education.com",
            #         "{FilenameWithExtension}": "john.smith@education.com",
            #         "{Path}": "Lists/2025 Participants/",
            #         "{FullPath}": "Lists/2025 Participants/615_.000",
            #         "{ContentType}": {
            #             "@odata.type": "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedContentType",
            #             "Id": "0x0100D97499FA4F06944DB3F296DB8C896C550039647431C4705A409B62E2883347CFBE",
            #             "Name": "Item"
            #         },
            #         "{ContentType}#Id": "0x0100D97499FA4F06944DB3F296DB8C896C550039647431C4705A409B62E2883347CFBE",
            #         "{HasAttachments}": false,
            #         "{VersionNumber}": "1.0"
            #     }
