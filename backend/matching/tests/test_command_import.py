# matching/tests/test_command_import.py
import io
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from matching.models import Student, Mentor, Interest, Track, Experience

@pytest.mark.django_db
@patch("matching.management.commands.import_p11.pd.read_excel")
@patch("matching.management.commands.import_p11.pd.ExcelFile")
def test_import_p11_happy_path(mock_excel_file, mock_read_excel):
    # 1) Prepare a fake ExcelFile (only sheet_names required)
    fake_xls = MagicMock()
    fake_xls.sheet_names = ["Students", "Mentors"]
    mock_excel_file.return_value = fake_xls

    # 2) Two memory DataFrames (use your alias set for column names)
    df_students = pd.DataFrame({
        "First Name": ["Alice"],
        "Last Name": ["Lee"],
        "Email": ["alice@example.com"],
        "Year Level": [9],
        "Country": ["AU"],
        "Region": ["NSW"],
        "Area(s) of Interest": ["AI, Bio"],
        "School Name": ["Sydney High"],
        "Group Number": ["G-01"],
    })
    df_mentors = pd.DataFrame({
        "First Name": ["Bob"],
        "Last Name": ["Smith"],
        "Email": ["bob@example.com"],
        "Background": ["Uni"],
        "Experience": ["Academic"],
        "Institution": ["USYD"],
        "Country": ["AU"],
        "Region": ["NSW"],
        "Track": [""],  # leave blank -> map_track
        "Area of Interest *": ["AI; Robotics"],
        "Maximum Number of Groups": [3],
    })

    def read_excel_side(xls, sheet_name, *_, **__):
        return df_students if sheet_name == "Students" else df_mentors
    mock_read_excel.side_effect = read_excel_side

    # 3) Run the command and capture the output
    buf = io.StringIO()
    call_command("import_p11", "dummy.xlsx", stdout=buf)
    out = buf.getvalue()
    assert "Import completed:" in out

    # 4) Assert that the data in the library is correct + normalized correctly
    assert Student.objects.count() == 1
    stu = Student.objects.get(email="alice@example.com")
    assert stu.first_name == "Alice"
    assert stu.track == Track.AUS_NSW
    assert stu.preassigned_group == "G-01"
    assert set(stu.interests.values_list("name", flat=True)) == {"Ai", "Bio"}

    assert Mentor.objects.count() == 1
    men = Mentor.objects.get(email="bob@example.com")
    assert men.experience == Experience.AC
    assert men.track == Track.AUS_NSW
    assert men.max_groups == 3
    assert set(men.interests.values_list("name", flat=True)) == {"Ai", "Robotics"}

    # The interest table contains at least these three
    assert set(Interest.objects.values_list("name", flat=True)) >= {"Ai", "Bio", "Robotics"}
