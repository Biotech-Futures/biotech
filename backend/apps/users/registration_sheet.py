"""Upload student details, from an .xlsx: a supervisor's spreadsheet as CSV
text, for the registration page to check as it checks a CSV it reads itself.
Only the first sheet is read, and nothing is saved here."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from openpyxl import load_workbook
from rest_framework import permissions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .registration_intake import authenticated_supervisor

# As the page's own limit on a CSV.
MAX_SHEET_BYTES = 2 * 1024 * 1024
NOT_READ = "This file couldn't be read as an .xlsx spreadsheet. Save it again, or upload a CSV."


def _text(value) -> str:
    """A cell as a CSV has it: a whole number without ".0", a date as
    2026-10-18, and an empty cell empty."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def sheet_as_csv(file) -> str:
    """The first sheet of an .xlsx as CSV text."""
    sheet = load_workbook(file, read_only=True, data_only=True).active
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in [] if sheet is None else sheet.iter_rows(values_only=True):
        writer.writerow([_text(value) for value in row])
    return buffer.getvalue()


class RegistrationSheetView(APIView):
    """POST multipart ``file`` (an .xlsx): ``{"csv": "<its first sheet>"}``.
    For a supervisor registering students, as the registration itself is."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser]

    def post(self, request):
        authenticated_supervisor(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": "Choose an .xlsx or .csv file."})
        if upload.size > MAX_SHEET_BYTES:
            raise serializers.ValidationError({"file": "Choose a file no larger than 2 MB."})
        try:
            text = sheet_as_csv(upload)
        except Exception:
            # Not a workbook (or a broken one): openpyxl's errors vary by how.
            raise serializers.ValidationError({"file": NOT_READ}) from None
        return Response({"csv": text})
