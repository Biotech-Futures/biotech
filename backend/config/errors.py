from rest_framework import status
from rest_framework.exceptions import APIException


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
