"""Submission API errors, in the same shape as ``config/errors.py``."""
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


class SubmissionLocked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "This entry has been submitted. Choose to resubmit before making changes."
    )
    default_code = "submission_locked"


class NotSubmittedYet(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This entry has not been submitted, so there is nothing to reopen."
    default_code = "not_submitted_yet"


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
        self.extra = {"missing": list(prompts)}


class PosterFormatRejected(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This poster is not in the required format."
    default_code = "poster_format_rejected"

    def __init__(self, problems):
        super().__init__()
        self.extra = {"problems": list(problems)}


class NoFileUploaded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "No file was included in the request."
    default_code = "no_file_uploaded"


class FileNotUploadedYet(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No file has been uploaded for this slot."
    default_code = "file_not_uploaded_yet"
