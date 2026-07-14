from django.test import TestCase

from apps.admin.services.user import create_user
from apps.groups.models import Countries, CountryStates
from apps.users.models import MentorProfile


class MentorReasonLengthTests(TestCase):
    """Regression: mentor_reason must accept paragraph-length reasons.

    The column was varchar(255) since 0001_initial, but real mentor "reason for
    mentoring" answers are 300-650 char essays and were rejected with
    'value too long for type character varying(255)'. mentor_reason is now a
    TextField (migration 0010_alter_mentorprofile_mentor_reason).
    """

    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        CountryStates.objects.create(country=country, state_name="NSW")

    def test_create_mentor_accepts_reason_longer_than_255_chars(self):
        reason = ("I want to mentor because I am passionate about inspiring the next "
                  "generation of STEM innovators. " * 6).strip()
        self.assertGreater(len(reason), 255)

        result = create_user({
            "email": "long-reason-mentor@example.com",
            "firstName": "Steph",
            "lastName": "Yee",
            "role": "mentor",
            "state": "NSW",
            "mentorInstitution": "Publicis CoLab",
            "mentorReason": reason,
            "mentorMaxGroupCount": 3,
            "interests": ["Biomedical Innovations"],
        })

        self.assertEqual(result["msg"], "User created successfully")
        self.assertIsNotNone(result["data"])

        # Persisted verbatim (no truncation) and round-trips through the API dict.
        stored = MentorProfile.objects.get(user_id=result["data"]["id"]).mentor_reason
        self.assertEqual(stored, reason)
        self.assertEqual(result["data"]["mentorReason"], reason)
