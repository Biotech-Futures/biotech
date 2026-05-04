from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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
    delete_resource, upload_resource, replace_resource_file, download_resource,
    assign_role_to_resource, remove_role_from_resource,
    list_resource_roles, list_resource_types, list_resource_tracks,
)
from apps.admin.services.announcement import (
    list_announcements, get_announcement_by_id, create_announcement,
    update_announcement, archive_announcement, send_announcement_email,
    list_announcement_tracks, list_announcement_roles,
)
from apps.admin.services.mentor import get_mentor_list, set_mentor_active
from apps.admin.services.mentor_match import (
    match_mentor, get_mentors, get_unmatched_groups, get_matched_groups,
    confirm_mentor_assignments, replace_mentor, bulk_replace_inactive_mentors,
    unassign_mentors,
)


# ============================================================================
# USER ENDPOINTS
# ============================================================================
class UserListCreateView(APIView):
    """GET /api/v1/user - List users with pagination and filters"""
    def get(self, request):
        active = request.query_params.get("active")
        if active is not None:
            active = active.lower() == "true"
        result = query_users(
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

    """POST /api/v1/user - Create single user"""
    def post(self, request):
        result = create_user(request.data)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class UserTracksListView(APIView):
    """GET /api/v1/user/tracks - List tracks available for filtering and assignment"""
    def get(self, request):
        result = query_tracks()
        return Response(result)


class UserDetailView(APIView):
    """GET /api/v1/user/{id} - Get single user"""
    def get(self, request, user_id):
        result = query_user_by_id(int(user_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/user/{id} - Update user info or role"""
    def put(self, request, user_id):
        result = update_user(int(user_id), request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    """DELETE /api/v1/user/{id} - Delete user"""
    def delete(self, request, user_id):
        result = delete_user(int(user_id))
        code = status.HTTP_200_OK if result.get("msg") == "User deleted successfully" else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class UserStatusUpdateView(APIView):
    """PATCH /api/v1/user/{id}/status - Activate or deactivate account"""
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
    """POST /api/v1/user/bulk - Bulk create users (JSON array)"""
    def post(self, request):
        users = request.data
        if not isinstance(users, list):
            return Response(
                {"msg": "Expected a JSON array of users", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = bulk_create_users(users, "")
        return Response(result, status=status.HTTP_201_CREATED)


class UserBulkCsvView(APIView):
    """POST /api/v1/user/bulk-csv - Bulk create users from CSV text"""
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
    """GET /api/v1/user/ungrouped-check - Check if there are ungrouped students"""
    def get(self, request):
        result = has_ungrouped_students()
        return Response({"msg": "Ungrouped students check completed", "data": {"hasUngrouped": result}})


# ============================================================================
# GROUP ENDPOINTS
# ============================================================================
class GroupListView(APIView):
    """GET /api/v1/group - List groups with pagination and filters"""
    def get(self, request):
        result = query_groups(
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 10)),
            search_name=request.query_params.get("searchName"),
            search_group=request.query_params.get("searchGroup"),
            track=request.query_params.get("track"),
            mentor_status=request.query_params.get("mentorStatus"),
        )
        return Response(result)


class GroupDetailView(APIView):
    """GET /api/v1/group/{id} - Get single group"""
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
    def get(self, request, group_id):
        result = query_group_messages(
            group_id,
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 50)),
        )
        return Response(result)


class GroupMessageDetailView(APIView):
    """DELETE /api/v1/group/{id}/messages/{messageId} - Remove a message from a group"""
    def delete(self, request, group_id, message_id):
        result = remove_group_message(group_id, int(message_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class GroupMemberRemoveView(APIView):
    """DELETE /api/v1/group/{id}/members/{userId} - Remove a student from a group"""
    def delete(self, request, group_id, user_id):
        result = remove_group_member(group_id, int(user_id))
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


# ============================================================================
# MATCH ENDPOINTS
# ============================================================================
class MatchStudentView(APIView):
    """GET /api/v1/match/student - Get match for authenticated user"""
    def get(self, request):
        uid = str(request.user.id) if request.user.is_authenticated else None
        if not uid:
            return Response({"msg": "Authentication required"}, status=401)
        result = match_student(uid)
        return Response({
            "msg": "Match retrieved successfully",
            "data": {
                "recommendations": result.recommendations,
                "unmatchedStudents": result.unmatched_students,
                "notFullGroups": result.not_full_groups,
            },
        })


class MatchIndividualView(APIView):
    """GET /api/v1/match/individual - Get individual students"""
    def get(self, request):
        result = get_individual_students()
        return Response({"msg": "Individual students retrieved successfully", "data": result})


class MatchConfirmView(APIView):
    """POST /api/v1/match/confirm - Confirm student assignments"""
    def post(self, request):
        result = confirm_student_assignments(request.data)
        return Response({"msg": "Assignments confirmed successfully", "data": result})


# ============================================================================
# EVENT ENDPOINTS
# ============================================================================
class EventListCreateView(APIView):
    """GET /api/v1/event - List events with pagination and filters"""
    def get(self, request):
        upcoming = request.query_params.get("upcoming", "false").lower() == "true"
        result = query_events({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "host_user_id": request.query_params.get("hostUserId"),
            "upcoming": upcoming,
        })
        return Response(result)

    """POST /api/v1/event - Create event"""
    def post(self, request):
        result = create_event(request.data)
        return Response(result, status=status.HTTP_201_CREATED)


class EventDetailView(APIView):
    """GET /api/v1/event/{id} - Get single event"""
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
    def put(self, request, rsvp_id):
        result = update_event_rsvp(rsvp_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class EventTargetsView(APIView):
    """GET /api/v1/event/{id}/targets - Get event targets"""
    def get(self, request, event_id):
        result = query_event_targets(event_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class EventMetaGroupsView(APIView):
    """GET /api/v1/event/meta/groups - List groups for event targeting"""
    def get(self, request):
        result = event_query_groups()
        return Response(result)


class EventMetaRolesView(APIView):
    """GET /api/v1/event/meta/roles - List roles for event targeting"""
    def get(self, request):
        result = event_query_roles()
        return Response(result)


class EventMetaTracksView(APIView):
    """GET /api/v1/event/meta/tracks - List tracks for event targeting"""
    def get(self, request):
        result = event_query_tracks()
        return Response(result)


# ============================================================================
# RESOURCE ENDPOINTS
# ============================================================================
class ResourceListCreateView(APIView):
    """GET /api/v1/resource - List resources with pagination and filters"""
    def get(self, request):
        result = query_resources({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "uploader_user_id": request.query_params.get("uploaderUserId"),
            "group_id": request.query_params.get("groupId"),
            "resource_kind": request.query_params.get("resourceKind"),
            "resource_type_id": request.query_params.get("resourceTypeId"),
            "resource_type": request.query_params.get("resourceType"),
            "track_id": request.query_params.get("trackId"),
            "search": request.query_params.get("search"),
            "order": request.query_params.get("order", "newest"),
            "uploader": request.query_params.get("uploader"),
            "role_slug": request.query_params.get("roleSlug"),
        })
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
    def get(self, request, resource_id):
        result = download_resource(resource_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class ResourceUploadView(APIView):
    """POST /api/v1/resource/upload - Upload resource file"""
    def post(self, request):
        uploader = None
        if hasattr(request, "user") and request.user.is_authenticated:
            uploader = {"id": str(request.user.id), "email": request.user.email}
        payload = {**request.data, "uploader": uploader}
        result = upload_resource(payload)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class ResourceFileReplaceView(APIView):
    """POST /api/v1/resource/{id}/upload - Replace resource file"""
    def post(self, request, resource_id):
        result = replace_resource_file(resource_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class ResourceRolesListView(APIView):
    """GET /api/v1/resource/roles - List available resource roles"""
    def get(self, request):
        result = list_resource_roles()
        return Response(result)


class ResourceTypesListView(APIView):
    """GET /api/v1/resource/types - List available resource types"""
    def get(self, request):
        result = list_resource_types()
        return Response(result)


class ResourceTracksListView(APIView):
    """GET /api/v1/resource/tracks - List available resource tracks"""
    def get(self, request):
        result = list_resource_tracks()
        return Response(result)


class ResourceAssignRoleView(APIView):
    """POST /api/v1/resource/{id}/assign-role - Assign role to resource"""
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
    def get(self, request):
        archived = request.query_params.get("archived")
        if archived is not None:
            archived = archived.lower() == "true"
        result = list_announcements({
            "page": int(request.query_params.get("page", 1)),
            "limit": int(request.query_params.get("limit", 10)),
            "search": request.query_params.get("search"),
            "archived": archived,
        })
        return Response(result)

    """POST /api/v1/announcement - Create announcement"""
    def post(self, request):
        author_user_id = None
        if hasattr(request, "user") and request.user.is_authenticated:
            author_user_id = request.user.id
        result = create_announcement(request.data, author_user_id)
        code = status.HTTP_201_CREATED if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementDetailView(APIView):
    """GET /api/v1/announcement/{id} - Get single announcement"""
    def get(self, request, announcement_id):
        result = get_announcement_by_id(announcement_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)

    """PUT /api/v1/announcement/{id} - Update announcement"""
    def put(self, request, announcement_id):
        result = update_announcement(announcement_id, request.data)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementArchiveView(APIView):
    """POST /api/v1/announcement/{id}/archive - Archive announcement"""
    def post(self, request, announcement_id):
        result = archive_announcement(announcement_id)
        code = status.HTTP_200_OK if result.get("data") else status.HTTP_404_NOT_FOUND
        return Response(result, status=code)


class AnnouncementNotifyView(APIView):
    """POST /api/v1/announcement/{id}/notify - Send announcement email notification"""
    def post(self, request, announcement_id):
        result = send_announcement_email(announcement_id)
        code = status.HTTP_200_OK if result.get("sent", 0) > 0 else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class AnnouncementTracksListView(APIView):
    """GET /api/v1/announcement/tracks - List available announcement tracks"""
    def get(self, request):
        result = list_announcement_tracks()
        return Response(result)


class AnnouncementRolesListView(APIView):
    """GET /api/v1/announcement/roles - List available announcement roles"""
    def get(self, request):
        result = list_announcement_roles()
        return Response(result)


# ============================================================================
# MENTOR ENDPOINTS
# ============================================================================
class MentorListView(APIView):
    """GET /api/v1/mentor - Get mentor list"""
    def get(self, request):
        mentors = get_mentor_list()
        return Response({"msg": "Mentors retrieved successfully", "data": mentors})


class MentorActiveStatusUpdateView(APIView):
    """PATCH /api/v1/mentor/{mentorId}/active - Update mentor active status"""
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
    def get(self, request):
        admin_user_id = str(request.user.id) if request.user.is_authenticated else None
        if not admin_user_id:
            return Response({"msg": "Authentication required"}, status=401)
        mode = request.query_params.get("mode", "balanced")
        result = match_mentor(admin_user_id, mode)
        return Response({"msg": "Mentor recommendations retrieved successfully", "data": result})


class MentorMatchMentorsListView(APIView):
    """GET /api/v1/mentor-match/mentors - Get list of mentors"""
    def get(self, request):
        result = get_mentors()
        return Response({"msg": "Mentors retrieved successfully", "data": result})


class MentorMatchGroupsListView(APIView):
    """GET /api/v1/mentor-match/groups - Get list of unmatched groups"""
    def get(self, request):
        result = get_unmatched_groups()
        return Response({"msg": "Unmatched groups retrieved successfully", "data": result})


class MentorMatchMatchedGroupsListView(APIView):
    """GET /api/v1/mentor-match/matched-groups - Get list of matched groups"""
    def get(self, request):
        result = get_matched_groups()
        return Response({"msg": "Matched groups retrieved successfully", "data": result})


class MentorMatchConfirmView(APIView):
    """POST /api/v1/mentor-match/confirm - Confirm mentor assignments"""
    def post(self, request):
        result = confirm_mentor_assignments(request.data)
        return Response({"msg": "Mentor assignments confirmed successfully", "data": result})


class MentorMatchReplaceView(APIView):
    """POST /api/v1/mentor-match/replace - Replace mentor assignment"""
    def post(self, request):
        result = replace_mentor(request.data)
        return Response({"msg": "Mentor replaced successfully", "data": result})


class MentorMatchBulkReplaceInactiveView(APIView):
    """POST /api/v1/mentor-match/bulk-replace-inactive - Replace all inactive mentor assignments"""
    def post(self, request):
        result = bulk_replace_inactive_mentors()
        return Response({"msg": "Inactive mentors replaced successfully", "data": result})


class MentorMatchUnassignView(APIView):
    """POST /api/v1/mentor-match/unassign - Unassign mentors from groups"""
    def post(self, request):
        group_ids = request.data.get("groupIds", [])
        result = unassign_mentors(group_ids)
        return Response({"msg": "Mentors unassigned successfully", "data": result})
