"""Upload student details, from an .xlsx: a supervisor's spreadsheet as CSV
text, for the registration page to check as it checks a CSV it reads itself.
Only the first sheet is read, and nothing is saved here. And the template the
page offers to download, as an .xlsx: its columns and example row, as the page
gives them (registrationTemplateRows), so they're said in one place."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework import permissions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .registration_intake import authenticated_supervisor

# As the page's own limit on a CSV.
MAX_SHEET_BYTES = 2 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEMPLATE_NAME = "biotech-registration-template.xlsx"
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


class TemplateInput(serializers.Serializer):
    # The header row, then the example row: the page's columns, in order.
    header = serializers.ListField(
        child=serializers.CharField(max_length=100), min_length=1, max_length=30,
    )
    example = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True), min_length=1, max_length=30,
    )
    # Beside the example row: that it's an example, and isn't registered.
    note = serializers.CharField(max_length=300)

    def validate(self, data):
        if len(data["example"]) != len(data["header"]):
            raise serializers.ValidationError({"example": "Give a value for each column."})
        return data


def template_xlsx(header, example, note) -> bytes:
    """The template: its header row in bold, the example row under it shaded
    (with ``note`` in the column after it, which uploads ignore), each column
    wide enough to read."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Students"
    sheet.append(header)
    sheet.append([*example, note])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DCEFE7")
    for cell in sheet[2]:
        cell.font = Font(italic=True, color="5F6B6A")
        cell.fill = PatternFill("solid", fgColor="FFF4CC")
    note_cell = sheet.cell(row=2, column=len(header) + 1)
    note_cell.font = Font(bold=True, color="8A5300")
    note_cell.fill = PatternFill(fill_type=None)
    note_cell.alignment = Alignment(wrap_text=False)
    for index, (title, value) in enumerate(zip(header, example), start=1):
        sheet.column_dimensions[get_column_letter(index)].width = max(len(title), len(value), 10) + 2
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


class RegistrationTemplateView(APIView):
    """POST ``{"header", "example", "note"}``: the template as an .xlsx to
    download. For a supervisor registering students, as uploading one is."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def post(self, request):
        authenticated_supervisor(request)
        parser = TemplateInput(data=request.data)
        parser.is_valid(raise_exception=True)
        data = parser.validated_data
        response = HttpResponse(template_xlsx(data["header"], data["example"], data["note"]), content_type=XLSX)
        response["Content-Disposition"] = f'attachment; filename="{TEMPLATE_NAME}"'
        return response
