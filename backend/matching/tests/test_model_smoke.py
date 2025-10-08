# matching/tests/test_models_smoke.py
import pytest
from matching.models import Student, Mentor, Interest, Track, Experience

@pytest.mark.django_db
def test_can_create_student_and_mentor_and_interests():
    s = Student.objects.create(
        first_name="Alice", last_name="Lee",
        email="alice@test.com", year_level=9,
        country="AU", region="NSW", track=Track.AUS_NSW,
    )
    m = Mentor.objects.create(
        first_name="Bob", last_name="Smith",
        email="bob@test.com", experience=Experience.AC,
        country="AU", region="NSW", track=Track.AUS_NSW,
        max_groups=2,
    )
    ai = Interest.objects.create(name="Ai")
    s.interests.add(ai)
    m.interests.add(ai)

    assert Student.objects.filter(pk=s.pk).exists()
    assert Mentor.objects.filter(pk=m.pk).exists()
    assert s.interests.count() == 1
    assert m.interests.count() == 1
