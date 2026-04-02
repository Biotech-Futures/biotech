# matching/tests/test_helpers.py
import pytest
from matching.management.commands.import_p11 import (
    norm, titleish, parse_interests, map_track, map_experience
)
from matching.models import Track, Experience

def test_norm_titleish():
    assert norm(None) == ""
    assert norm("  Ivy  ") == "Ivy"
    assert titleish("  bio   inFORMATICS ") == "Bio Informatics"

def test_parse_interests():
    raw = "AI, Robotics; biology / Bio|"
    assert parse_interests(raw) == ["Ai", "Robotics", "Biology", "Bio"]

@pytest.mark.parametrize("country,region,expected", [
    ("AU", "NSW", Track.AUS_NSW),
    ("Australia", "QLD", Track.AUS_QLD),
    ("AU", "Western Australia", Track.AUS_WA),
    ("Brazil", "SP", Track.BRA),
    ("??", "", Track.GLOBAL),
])
def test_map_track(country, region, expected):
    assert map_track(country, region) == expected

@pytest.mark.parametrize("raw,expected", [
    ("Undergraduate", Experience.UG),
    ("Postgraduate",  Experience.PG),
    ("HDR",           Experience.HDR),
    ("Academic",      Experience.AC),
    ("Industry",      Experience.IN),
    ("ug",            Experience.UG),
    ("unknown",       Experience.UG),  # default UG
    ("",              Experience.UG),
])
def test_map_experience(raw, expected):
    assert map_experience(raw) == expected
