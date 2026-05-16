from django.contrib.auth import update_session_auth_hash
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils import timezone
from pathlib import PurePosixPath
import re
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped

from apps.admin.services.user import (
    query_users, query_user_by_id, query_tracks,
    create_user, bulk_create_users, update_user, update_status, delete_user,
    has_ungrouped_students,
)
from apps.admin.services.group import (
    query_groups, query_group_by_id, query_group_messages,
    update_group, remove_group_member, remove_group_message,
)
from apps.admin.services.match import (
    match_student, get_individual_students, confirm_student_assignments,
)
from apps.admin.services.event import (
    query_events, query_event_by_id, create_event, update_event, delete_event,
    query_event_rsvps, create_event_rsvp, update_event_rsvp,
    query_event_targets, query_groups as event_query_groups,
    query_roles as event_query_roles, query_tracks as event_query_tracks,
)
from apps.admin.services.resource import (
    query_resources, query_resource_by_id, create_resource, update_resource,
    delete_resource, replace_resource_file, download_resource, access_resource,
    assign_role_to_resource, remove_role_from_resource,
    list_resource_roles, list_resource_types, list_resource_tracks,
)
from apps.resources.services.upload import upload_resource_file
from apps.resources.models import Resources
from apps.common.filenames import sanitize_upload_filename
from apps.common.upload_validation import validate_uploaded_file
from apps.admin.services.announcement import (
    list_announcements, get_announcement_by_id, create_announcement,
    update_announcement, archive_announcement, send_announcement_email,
    list_announcement_tracks, list_announcement_roles,
)
from apps.admin.services.mentor import get_mentor_list, set_mentor_active
from apps.admin.services.task import (
    list_admin_tasks, get_admin_task_by_id, create_admin_task,
    update_admin_task, delete_admin_task, toggle_admin_task,
)
from apps.admin.services.mentor_match import (
    match_mentor, get_mentors, get_unmatched_groups, get_matched_groups,
    confirm_mentor_assignments, replace_mentor, bulk_replace_inactive_mentors,
    unassign_mentors,
)


# ============================================================================
# USER ENDPOINTS
# ============================================================================
class UserListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        active = request.query_params.get("active")
        if active is not None:
            active = active.lower() == "true"
        result = query_users(
            requesting_user=request.user,
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 10)),
            search=request.query_params.get("search"),
            role=request.query_params.get("role"),
            track=request.query_params.get("track"),
            active=active,
            in_group=request.query_params.get("inGroup"),
            sort_by=request.query_params.get("sortBy", "createdAt"),
            sort_order=request.query_params.get("sortOrder", "desc"),
        )
        return Response(result)

    def post(self, request):
        result = create_user(request.data)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class UserTracksListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = query_tracks(requesting_user=request.user)
        return Response(result)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, user_id):
        result = query_user_by_id(int(user_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    def put(self, request, user_id):
        result = update_user(int(user_id), request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    def delete(self, request, user_id):
        result = delete_user(int(user_id))
        code = status.HTTP_200_OK if result.get("msg") == "User deleted successfully" else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class UserStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def patch(self, request, user_id):
        is_active = request.data.get("isActive")
        if is_active is None:
            return Response(
                {"msg": "isActive field is required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = update_status(int(user_id), is_active)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class UserBulkCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        users = (
            request.data.get("users")
            if isinstance(request.data, dict)
            else request.data
        )
        if not isinstance(users, list):
            return Response(
                {"msg": "Expected a JSON array of users", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = bulk_create_users(users, "")
        return Response(result, status=status.HTTP_201_CREATED)


class UserBulkCsvView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        csv_text = request.data.get("csv", "")
        if not csv_text:
            return Response(
                {"msg": "CSV data is required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        import csv
        import io
        reader = csv.DictReader(io.StringIO(csv_text))
        users = list(reader)
        result = bulk_create_users(users, "")
        return Response(result, status=status.HTTP_201_CREATED)


class UserUngroupedCheckView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = has_ungrouped_students()
        return Response({"msg": "Ungrouped students check completed", "data": {"hasUngrouped": result}})


# ============================================================================
# GROUP ENDPOINTS
# ============================================================================
class GroupListView(APIView):
    """GET /api/v1/group - List groups with pagination and filters"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = query_groups(
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 10)),
            search_name=request.query_params.get("searchName"),
            search_group=request.query_params.get("searchGroup"),
            track=request.query_params.get("track"),
            mentor_status=request.query_params.get("mentorStatus"),
            requesting_user=request.user,
        )
        return Response(result)


class GroupDetailView(APIView):
    """GET /api/v1/group/{id} - Get single group"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, group_id):
        result = query_group_by_id(group_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/group/{id} - Update group"""
    def put(self, request, group_id):
        result = update_group(
            group_id,
            name=request.data.get("name"),
            track=request.data.get("track"),
        )
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class GroupMessagesListView(APIView):
    """GET /api/v1/group/{id}/messages - View group message history"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, group_id):
        result = query_group_messages(
            group_id,
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 50)),
        )
        return Response(result)


class GroupMessageDetailView(APIView):
    """DELETE /api/v1/group/{id}/messages/{messageId} - Remove a message from a group"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def delete(self, request, group_id, message_id):
        result = remove_group_message(group_id, int(message_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class GroupMemberRemoveView(APIView):
    """DELETE /api/v1/group/{id}/members/{userId} - Remove a student from a group"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def delete(self, request, group_id, user_id):
        result = remove_group_member(group_id, int(user_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


# ============================================================================
# MATCH ENDPOINTS
# ============================================================================
class MatchStudentView(APIView):
    """GET /api/v1/match/student - Get match for authenticated user"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        uid = str(request.user.id) if request.user.is_authenticated else None
        if not uid:
            return Response({"msg": "Authentication required"}, status=401)
        result = match_student(uid)
        return Response({
            "msg": "Match retrieved successfully",
            "data": {
                "recommendations": result.recommendations,
                "unmatched_students": result.unmatched_students,
                "not_full_groups": result.not_full_groups,
            },
        })


class MatchIndividualView(APIView):
    """GET /api/v1/match/individual - Get individual students"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = get_individual_students()
        return Response({"msg": "Individual students retrieved successfully", "data": result})


class MatchConfirmView(APIView):
    """POST /api/v1/match/confirm - Confirm student assignments"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        result = confirm_student_assignments(request.data)
        return Response({"msg": "Assignments confirmed successfully", "data": result})


# ============================================================================
# EVENT ENDPOINTS
# ============================================================================
class EventListCreateView(APIView):
    """GET /api/v1/event - List events with pagination and filters"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        upcoming = request.query_params.get("upcoming", "false").lower() == "true"
        result = query_events({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "host_user_id": request.query_params.get("hostUserId"),
            "upcoming": upcoming,
        }, requesting_user=request.user)
        return Response(result)

    """POST /api/v1/event - Create event"""
    def post(self, request):
        result = create_event(request.data, requesting_user=request.user)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class EventDetailView(APIView):
    """GET /api/v1/event/{id} - Get single event"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, event_id):
        result = query_event_by_id(event_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/event/{id} - Update event"""
    def put(self, request, event_id):
        result = update_event(event_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    """DELETE /api/v1/event/{id} - Delete event"""
    def delete(self, request, event_id):
        result = delete_event(event_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class EventRsvpListCreateView(APIView):
    """GET /api/v1/event/{id}/rsvp - Get event RSVPs"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, event_id):
        result = query_event_rsvps(event_id)
        return Response(result)

    """POST /api/v1/event/{id}/rsvp - Create event RSVP"""
    def post(self, request, event_id):
        result = create_event_rsvp(event_id, request.data)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class EventRsvpDetailView(APIView):
    """PUT /api/v1/event/rsvp/{rsvpId} - Update event RSVP"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def put(self, request, rsvp_id):
        result = update_event_rsvp(rsvp_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class EventTargetsView(APIView):
    """GET /api/v1/event/{id}/targets - Get event targets"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, event_id):
        result = query_event_targets(event_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class EventMetaGroupsView(APIView):
    """GET /api/v1/event/meta/groups - List groups for event targeting"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = event_query_groups(requesting_user=request.user)
        return Response(result)


class EventMetaRolesView(APIView):
    """GET /api/v1/event/meta/roles - List roles for event targeting"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = event_query_roles()
        return Response(result)


class EventMetaTracksView(APIView):
    """GET /api/v1/event/meta/tracks - List tracks for event targeting"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = event_query_tracks(requesting_user=request.user)
        return Response(result)


# ============================================================================
# RESOURCE ENDPOINTS
# ============================================================================
class ResourceListCreateView(APIView):
    """GET /api/v1/resource - List resources with pagination and filters"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = query_resources({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "uploader_user_id": request.query_params.get("uploaderUserId"),
            "group_id": request.query_params.get("groupId"),
            "resource_kind": (
                request.query_params.get("resourceKind")
                or request.query_params.get("resource_kind")
            ),
            "resource_type_id": request.query_params.get("resourceTypeId"),
            "resource_type": (
                request.query_params.get("resourceType")
                or request.query_params.get("resource_type")
            ),
            "track_id": (
                request.query_params.get("trackId")
                or request.query_params.get("track_id")
            ),
            "search": request.query_params.get("search"),
            "order": request.query_params.get("order", "newest"),
            "uploader": request.query_params.get("uploader"),
            "role_slug": request.query_params.get("roleSlug"),
        }, requesting_user=request.user)
        return Response(result)

    """POST /api/v1/resource - Create resource"""
    def post(self, request):
        uploader = None
        if hasattr(request, "user") and request.user.is_authenticated:
            uploader = {"id": str(request.user.id), "email": request.user.email}
        result = create_resource(request.data, uploader)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class ResourceDetailView(APIView):
    """GET /api/v1/resource/{id} - Get single resource"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, resource_id):
        result = query_resource_by_id(resource_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/resource/{id} - Update resource"""
    def put(self, request, resource_id):
        result = update_resource(resource_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    """PATCH /api/v1/resource/{id} - Update resource (partial)"""
    def patch(self, request, resource_id):
        result = update_resource(resource_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    """DELETE /api/v1/resource/{id} - Delete resource"""
    def delete(self, request, resource_id):
        result = delete_resource(resource_id)
        code = status.HTTP_200_OK if result.get("msg") == "Resource deleted successfully" else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class ResourceDownloadView(APIView):
    """GET /api/v1/resource/{id}/download - Download resource file"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, resource_id):
        result = download_resource(resource_id)
        data = result.get("data")
        if not data:
            return Response(result, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(
            data["content"],
            content_type=data.get("mime_type") or "application/octet-stream",
        )
        response["Content-Disposition"] = f'attachment; filename="{data["file_name"]}"'
        return response


class ResourceAccessView(APIView):
    """GET /api/v1/resource/{id}/access - Stream resource content inline"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, resource_id):
        result = access_resource(resource_id)
        data = result.get("data")
        if not data:
            return Response(result, status=status.HTTP_404_NOT_FOUND)

        response = StreamingHttpResponse(
            data["stream"],
            content_type=data.get("mime_type") or "application/octet-stream",
        )
        response["Content-Disposition"] = f'inline; filename="{data["file_name"]}"'
        response["Cache-Control"] = "private, max-age=300"
        if data.get("file_size") is not None:
            response["Content-Length"] = str(data["file_size"])
        return response


class ResourceUploadView(APIView):
    """POST /api/v1/resource/upload - Upload resource file"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        try:
            resource = upload_resource_file(
                data=request.data,
                files=request.FILES,
                user=request.user,
            )
        except ValidationError as exc:
            return Response(
                {"msg": "Failed to upload resource", "errors": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"msg": str(exc), "data": None}, status=status.HTTP_400_BAD_REQUEST)

        result = query_resource_by_id(resource.id)
        return Response(result, status=status.HTTP_201_CREATED)


class ResourceFileReplaceView(APIView):
    """POST /api/v1/resource/{id}/upload - Replace resource file"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request, resource_id):
        result = replace_resource_file(resource_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class ResourceRolesListView(APIView):
    """GET /api/v1/resource/roles - List available resource roles"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = list_resource_roles()
        return Response(result)


class ResourceTypesListView(APIView):
    """GET /api/v1/resource/types - List available resource types"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = list_resource_types()
        return Response(result)


class ResourceTracksListView(APIView):
    """GET /api/v1/resource/tracks - List available resource tracks"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = list_resource_tracks(requesting_user=request.user)
        return Response(result)


class ResourceAssignRoleView(APIView):
    """POST /api/v1/resource/{id}/assign-role - Assign role to resource"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request, resource_id):
        role_id = request.data.get("roleId")
        if role_id is None:
            return Response(
                {"msg": "roleId is required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = assign_role_to_resource(resource_id, role_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class ResourceRemoveRoleView(APIView):
    """DELETE /api/v1/resource/{id}/remove-role - Remove role from resource"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def delete(self, request, resource_id):
        role_id = request.data.get("roleId")
        if role_id is None:
            return Response(
                {"msg": "roleId is required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = remove_role_from_resource(resource_id, role_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


# ============================================================================
# ANNOUNCEMENT ENDPOINTS
# ============================================================================
class AnnouncementListCreateView(APIView):
    """GET /api/v1/announcement - List announcements with pagination and filters"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        archived = request.query_params.get("archived")
        if archived is not None:
            archived = archived.lower() == "true"
        result = list_announcements({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "search": request.query_params.get("search"),
            "archived": archived,
        }, requesting_user=request.user)
        return Response(result)

    """POST /api/v1/announcement - Create announcement"""
    def post(self, request):
        # ``initiated_by`` carries the acting user; ``create_announcement``
        # derives ``author_user_id`` from it. The two are split in the
        # service signature so impersonation / service-account flows can
        # still pass a different ``author_user_id`` if needed — see
        # ``_resolve_author_user_id`` in apps.admin.services.announcement.
        initiated_by = (
            request.user
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )
        result = create_announcement(request.data, initiated_by=initiated_by)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementDetailView(APIView):
    """GET /api/v1/announcement/{id} - Get single announcement"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, announcement_id):
        result = get_announcement_by_id(announcement_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/announcement/{id} - Update announcement"""
    def put(self, request, announcement_id):
        initiated_by = (
            request.user
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )
        result = update_announcement(
            announcement_id, request.data, initiated_by=initiated_by,
        )
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementArchiveView(APIView):
    """POST /api/v1/announcement/{id}/archive - Archive announcement"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request, announcement_id):
        result = archive_announcement(announcement_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class AnnouncementNotifyView(APIView):
    """POST /api/v1/announcement/{id}/notify - Send announcement email notification"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request, announcement_id):
        initiated_by = (
            request.user
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )
        result = send_announcement_email(
            announcement_id, initiated_by=initiated_by,
        )

        delivery_status = result.get("status")
        # 200 — every recipient accepted.
        # 207 — at least one delivered, at least one failed (Multi-Status).
        # 502 — mail backend was reached but no recipient accepted (or the
        #       backend itself errored) — distinguishes "broken pipe to SMTP"
        #       from a client-side validation problem.
        # 400 — no recipients to send to, or the announcement does not exist.
        if delivery_status == "success":
            code = status.HTTP_200_OK
        elif delivery_status == "partial":
            code = status.HTTP_207_MULTI_STATUS
        elif delivery_status == "failed":
            code = status.HTTP_502_BAD_GATEWAY
        else:  # "skipped" — no recipients / unknown announcement
            code = status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementTracksListView(APIView):
    """GET /api/v1/announcement/tracks - List available announcement tracks"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = list_announcement_tracks(requesting_user=request.user)
        return Response(result)


class AnnouncementRolesListView(APIView):
    """GET /api/v1/announcement/roles - List available announcement roles"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = list_announcement_roles()
        return Response(result)


class ResourceAttachmentUploadView(APIView):
    """POST /api/v1/admin/resource/attachments/ - Upload a file for editor links"""
    permission_classes = [IsAuthenticated, IsAdminScoped]
    parser_classes = [MultiPartParser, FormParser]

    storage_prefix = "resource_attachments"
    field_label = "Resource attachment"
    fallback_name = "resource-attachment"
    description_prefix = "Resource attachment"
    download_route_name = "admin_api:resource-attachment-download"

    def _storage(self):
        media_url = getattr(settings, "MEDIA_URL", "/media/").rstrip("/") + "/"
        return FileSystemStorage(
            location=settings.MEDIA_ROOT / self.storage_prefix,
            base_url=f"{media_url}{self.storage_prefix}/",
        )

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"msg": "No file was uploaded.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_uploaded_file(
                uploaded_file,
                max_size=settings.RESOURCE_FILE_MAX_UPLOAD_SIZE,
                allowed_extensions=settings.RESOURCE_FILE_ALLOWED_EXTENSIONS,
                allowed_mime_types=settings.RESOURCE_FILE_ALLOWED_MIME_TYPES,
                field_label=self.field_label,
            )
        except ValidationError as exc:
            return Response(
                {"msg": "Failed to upload attachment", "errors": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_name = sanitize_upload_filename(
            getattr(uploaded_file, "name", "") or self.fallback_name
        )
        name = base_name[:220] or self.fallback_name
        if Resources.objects.filter(name__iexact=name, deleted_at__isnull=True).exists():
            name = f"{name[:180]} ({timezone.now().strftime('%Y%m%d%H%M%S')})"

        saved_name = self._storage().save(
            f"{timezone.now().strftime('%Y/%m/%d')}/{timezone.now().strftime('%H%M%S%f')}-{base_name}",
            uploaded_file,
        )
        resource = Resources.objects.create(
            name=name,
            description=f"{self.description_prefix}: {base_name}"[:255],
            kind="attachment",
            visibility_scope=Resources.VisibilityScope.PUBLIC,
            uploaded_by=request.user,
            storage_key=f"{self.storage_prefix}/{saved_name}",
            file_mime_type=getattr(uploaded_file, "content_type", None) or None,
            file_size=getattr(uploaded_file, "size", None),
        )

        resource_url = request.build_absolute_uri(self._storage().url(saved_name))
        download_url = reverse(
            self.download_route_name,
            kwargs={"resource_id": resource.pk},
            request=request,
        )
        return Response(
            {
                "msg": "Attachment uploaded successfully",
                "data": {
                    "id": resource.id,
                    "kind": resource.kind,
                    "fileName": base_name,
                    "url": resource_url,
                    "resourceUrl": resource_url,
                    "downloadUrl": download_url,
                    "mimeType": resource.file_mime_type,
                    "size": resource.file_size,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ResourceAttachmentDownloadView(APIView):
    """GET /api/v1/admin/resource/attachments/{id}/download/"""
    permission_classes = [IsAuthenticated]
    storage_prefix = "resource_attachments"
    stored_filename_prefix_re = re.compile(r"^\d+-")

    def _storage(self):
        return FileSystemStorage(location=settings.MEDIA_ROOT / self.storage_prefix)

    def _download_filename(self, resource, saved_name):
        stored_name = PurePosixPath(saved_name).name
        original_name = self.stored_filename_prefix_re.sub("", stored_name, count=1)
        return sanitize_upload_filename(original_name or resource.name)

    def get(self, request, resource_id):
        resource = Resources.objects.filter(
            id=resource_id,
            kind="attachment",
            deleted_at__isnull=True,
        ).first()
        if resource is None or not resource.storage_key:
            return Response(
                {"msg": "Attachment not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        prefix = f"{self.storage_prefix}/"
        if not resource.storage_key.startswith(prefix):
            return Response(
                {"msg": "Attachment storage target is invalid", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        saved_name = resource.storage_key[len(prefix):]
        try:
            file_handle = self._storage().open(saved_name, "rb")
        except Exception:
            return Response(
                {"msg": "Attachment file not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=self._download_filename(resource, saved_name),
        )
        if resource.file_mime_type:
            response["Content-Type"] = resource.file_mime_type
        return response


class AnnouncementAttachmentUploadView(ResourceAttachmentUploadView):
    """Legacy announcement attachment route kept for existing rich content links."""

    storage_prefix = "announcement_attachments"
    field_label = "Announcement attachment"
    fallback_name = "announcement-attachment"
    description_prefix = "Announcement attachment"
    download_route_name = "admin_api:announcement-attachment-download"


class AnnouncementAttachmentDownloadView(ResourceAttachmentDownloadView):
    """Legacy announcement attachment download route."""

    storage_prefix = "announcement_attachments"


# ============================================================================
# MENTOR ENDPOINTS
# ============================================================================
class MentorListView(APIView):
    """GET /api/v1/mentor - Get mentor list"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        mentors = get_mentor_list(requesting_user=request.user)
        return Response({"msg": "Mentors retrieved successfully", "data": mentors})


class MentorActiveStatusUpdateView(APIView):
    """PATCH /api/v1/mentor/{mentorId}/active - Update mentor active status"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def patch(self, request, mentor_id):
        is_active = request.data.get("isActive")
        if is_active is None:
            return Response(
                {"msg": "isActive field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = set_mentor_active(mentor_id, is_active)
        return Response({"msg": "Mentor status updated successfully", "data": result})


# ============================================================================
# MENTOR MATCH ENDPOINTS
# ============================================================================
class MentorMatchRecommendView(APIView):
    """GET /api/v1/mentor-match/recommend - Get mentor recommendations"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        admin_user_id = str(request.user.id) if request.user.is_authenticated else None
        if not admin_user_id:
            return Response({"msg": "Authentication required"}, status=401)
        raw_mode = request.query_params.get("mode")
        mode = raw_mode if raw_mode in ("strict", "coverage") else "balanced"
        result = match_mentor(admin_user_id, mode)
        return Response({"msg": "Mentor recommendations retrieved successfully", "data": result})


class MentorMatchMentorsListView(APIView):
    """GET /api/v1/mentor-match/mentors - Get list of mentors"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = get_mentors(requesting_user=request.user)
        return Response({"msg": "Mentors retrieved successfully", "data": result})


class MentorMatchGroupsListView(APIView):
    """GET /api/v1/mentor-match/groups - Get list of unmatched groups"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = get_unmatched_groups(requesting_user=request.user)
        return Response({"msg": "Unmatched groups retrieved successfully", "data": result})


class MentorMatchMatchedGroupsListView(APIView):
    """GET /api/v1/mentor-match/matched-groups - Get list of matched groups"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        result = get_matched_groups(requesting_user=request.user)
        return Response({"msg": "Matched groups retrieved successfully", "data": result})


class MentorMatchConfirmView(APIView):
    """POST /api/v1/mentor-match/confirm - Confirm mentor assignments"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        result = confirm_mentor_assignments(request.data)
        return Response({"msg": "Mentor assignments confirmed successfully", "data": result})


class MentorMatchReplaceView(APIView):
    """POST /api/v1/mentor-match/replace - Replace mentor assignment"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        result = replace_mentor(request.data)
        return Response({"msg": "Mentor replaced successfully", "data": result})


class MentorMatchBulkReplaceInactiveView(APIView):
    """POST /api/v1/mentor-match/bulk-replace-inactive - Replace all inactive mentor assignments"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        result = bulk_replace_inactive_mentors()
        return Response({"msg": "Inactive mentors replaced successfully", "data": result})


class MentorMatchUnassignView(APIView):
    """POST /api/v1/mentor-match/unassign - Unassign mentors from groups"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request):
        group_ids = request.data.get("groupIds", [])
        result = unassign_mentors(group_ids)
        return Response({"msg": "Mentors unassigned successfully", "data": result})


# ============================================================================
# TASK ENDPOINTS
# ============================================================================
class AdminTaskListCreateView(APIView):
    """GET /api/v1/admin/task/ — List tasks visible to admin"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request):
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))
        task_type = request.query_params.get("task_type") or None
        result = list_admin_tasks(request.user, page=page, limit=limit, task_type=task_type)
        return Response(result)

    def post(self, request):
        result = create_admin_task(request.user, request.data)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AdminTaskDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/admin/task/{task_id}/ — Task detail"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def get(self, request, task_id):
        result = get_admin_task_by_id(request.user, task_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    def patch(self, request, task_id):
        result = update_admin_task(request.user, task_id, request.data)
        if result.get("msg") == "Task not found":
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result)

    def delete(self, request, task_id):
        result = delete_admin_task(request.user, task_id)
        if result.get("msg") == "Task not found":
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_204_NO_CONTENT)


class AdminTaskToggleView(APIView):
    """POST /api/v1/admin/task/{task_id}/toggle/ — Toggle task completion"""
    permission_classes = [IsAuthenticated, IsAdminScoped]

    def post(self, request, task_id):
        completed = request.data.get("completed")
        if completed is None:
            return Response(
                {"msg": "completed field is required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = toggle_admin_task(request.user, task_id, bool(completed))
        if result.get("msg") == "Task not found":
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


# ============================================================================
# ADMIN AUTH ENDPOINTS
# ============================================================================
class AdminPasswordStatusView(APIView):
    """GET /api/v1/admin/auth/password-status/ — check if user has a usable password."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "msg": "Password status retrieved",
            "data": {"hasPassword": request.user.has_usable_password()},
        })


class AdminSetPasswordView(APIView):
    """POST /api/v1/admin/auth/set-password/ — set password for first-time admin."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.has_usable_password():
            return Response(
                {"msg": "Password is already set", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        password = request.data.get("password", "")
        if not password or len(password) < 8:
            return Response(
                {"msg": "Password must be at least 8 characters", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        return Response({"msg": "Password set successfully", "data": True})
