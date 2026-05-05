from typing import Type

from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import APIException


def error_json_response(exc_class: Type[APIException]) -> JsonResponse:
    return JsonResponse(
        {"error": exc_class.default_detail, "code": exc_class.default_code},
        status=exc_class.status_code,
    )


class EmailRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Email is required."
    default_code = "email_required"


class EmailAndCodeRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Email and code are required."
    default_code = "email_and_code_required"


class InvalidOrExpiredCode(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid or expired code."
    default_code = "invalid_or_expired_code"


class InvalidCredentials(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class AccountInactive(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Account is inactive."
    default_code = "account_inactive"


class OperationalAdminRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Operational admin access is required."
    default_code = "operational_admin_required"


class UserNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "User not found."
    default_code = "user_not_found"


class TooManyFailedAttempts(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many failed attempts. Try again in 5 minutes."
    default_code = "too_many_failed_attempts"


class GroupAccessDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have access to this group."
    default_code = "group_access_denied"


class AdminVerificationRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Only admins can verify certificates."
    default_code = "admin_verification_required"


class AdminScopeForTrackRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have admin scope for the target track."
    default_code = "admin_scope_for_track_required"


class AdminScopeForUserRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "admin_scope_for_user_required"

    def __init__(self, user_id):
        super().__init__(detail=f"You do not have admin scope for user {user_id}.")
        self.extra = {"target_user_id": user_id}


class MissingUsers(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "One or more user IDs were not found."
    default_code = "missing_users"

    def __init__(self, missing_user_ids):
        super().__init__()
        self.extra = {"missing_user_ids": list(missing_user_ids)}


class UserAndRoleIdRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "user_id and role_id are required."
    default_code = "user_and_role_id_required"


class RoleIdRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "role_id is required."
    default_code = "role_id_required"


class RoleNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Role not found."
    default_code = "role_not_found"


class RoleAlreadyAssigned(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Role is already assigned to this resource."
    default_code = "role_already_assigned"


class RoleNotAssigned(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Role is not assigned to this resource."
    default_code = "role_not_assigned"


class ClosedAssignmentImmutable(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cannot modify a closed assignment."
    default_code = "closed_assignment_immutable"


class RoleCreationFailed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Role creation failed."
    default_code = "role_creation_failed"


class UserHasActiveRoles(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "User already has active roles."
    default_code = "user_has_active_roles"

    def __init__(self, existing_roles):
        super().__init__()
        self.extra = {
            "existing_roles": list(existing_roles),
            "suggestion": (
                "Set 'revoke_others': true to revoke existing roles, "
                "or 'force': true to allow multiple roles."
            ),
        }


class ResourcePermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Permission denied."
    default_code = "resource_permission_denied"

    def __init__(self, reason=None):
        super().__init__()
        if reason:
            self.extra = {"reason": reason}
