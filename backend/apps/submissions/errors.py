"""Submission-specific API errors.

Follows the shape used in ``config/errors.py`` (a ``default_detail`` plus a
stable machine-readable ``default_code``) but stays app-local, so adding the
submission feature does not require editing a shared module. Errors that
already exist centrally — notably ``GroupAccessDenied`` — are reused rather
than duplicated here.
"""
from rest_framework import status
from rest_framework.exceptions import APIException


class SubmissionsClosed(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "The submission deadline for this team has passed."
    default_code = "submissions_closed"


class SubmissionsNotConfigured(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Submissions are not open yet."
    default_code = "submissions_not_configured"


class StudentRoleRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Only students in this team can edit its submission."
    default_code = "student_role_required"


class PosterRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A poster must be uploaded before the entry can be submitted."
    default_code = "poster_required"


class RequiredAnswersMissing(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Some required questions have not been answered."
    default_code = "required_answers_missing"

    def __init__(self, prompts):
        super().__init__()
        # Naming the questions lets the page point at them rather than making
        # the student hunt for which one is blank.
        self.extra = {"missing": list(prompts)}


class NoFileUploaded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "No file was included in the request."
    default_code = "no_file_uploaded"


class FileNotUploadedYet(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No file has been uploaded for this slot."
    default_code = "file_not_uploaded_yet"
