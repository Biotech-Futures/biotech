"""A mentor registering on the public registration page
(apps.users.mentor_registration): saved as an admin's Import Mentors saves
one, pending until an admin activates them, with their registration email."""
import uuid
from datetime import time

from django.core import mail
from django.test import TestCase, override_settings

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import MentorProfile, RegistrationSubmission, User, UserInterest
from apps.users.models.mentor_availability import MentorAvailability
from tests.apps.users.test_registration_latelink import RegistrationSetup

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def mentor_body(**changes):
    mentor = {
        "firstName": "Jordan", "lastName": "Ng", "email": "Jordan.Ng@uni.example.test",
        "country": "Australia", "state": "NSW",
        "affiliation": "postgraduate", "institution": "University of Sydney", "company": "",
        "universityYear": "2", "fieldOfStudy": "Bioengineering",
        "interests": ["Biomedical Innovations", "AI & Robotics and Smart Systems"],
        "capacity": "3",
        "background": "Two years of lab work on tissue scaffolds.",
        "motivation": "I'd like to help students find their way into research.",
        "mentoringApproach": "Weekly check-ins and pointing them to good sources.",
        "availability": [
            {"weekday": "0", "start": "17:00", "end": "18:30"},
            {"weekday": "", "start": "", "end": ""},
            {"weekday": "3", "start": "09:00", "end": "10:00"},
        ],
    }
    mentor.update(changes)
    return {"journey": "mentor", "payload": {"mentor": mentor}}


@override_settings(EMAIL_BACKEND=LOCMEM)
class MentorRegistrationTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")
        mail.outbox = []

    def register(self, body=None, **kwargs):
        return self.submit(body=body or mentor_body(), **kwargs)

    def test_a_mentor_is_saved_with_everything_the_form_gives(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        # As the form checks it: a mentor's receipt counts no students.
        self.assertEqual((response.data["journey"], response.data["student_count"]), ("mentor", 0))

        user = User.objects.get(email="jordan.ng@uni.example.test")
        # Pending until an admin activates them on Admin > Mentors.
        self.assertEqual((user.account_status, user.is_active), (User.AccountStatus.PENDING, False))
        self.assertEqual((user.first_name, user.last_name, user.country.country_name), ("Jordan", "Ng", "Australia"))
        self.assertTrue(RoleAssignmentHistory.objects.filter(user=user, role__role_name="mentor", valid_to=None).exists())
        profile = MentorProfile.objects.get(user=user)
        self.assertEqual(
            (profile.background, profile.institution, profile.company, profile.university_year,
             profile.field_of_study, profile.max_group_count),
            ("postgraduate", "University of Sydney", "", "2", "Bioengineering", 3),
        )
        self.assertEqual(profile.mentor_reason, "I'd like to help students find their way into research.")
        self.assertEqual(profile.relevant_background, "Two years of lab work on tissue scaffolds.")
        self.assertEqual(profile.mentoring_approach, "Weekly check-ins and pointing them to good sources.")
        self.assertEqual(
            sorted(UserInterest.objects.filter(user=user).values_list("interest__interest_desc", flat=True)),
            ["AI & Robotics and Smart Systems", "Biomedical Innovations"],
        )
        # The empty row is dropped.
        self.assertEqual(
            sorted(MentorAvailability.objects.filter(mentor_user=user).values_list("weekday", "start_time", "end_time")),
            [(0, time(17, 0), time(18, 30)), (3, time(9, 0), time(10, 0))],
        )
        submission = RegistrationSubmission.objects.get(reference=response.data["reference_code"])
        self.assertEqual((submission.journey, submission.student, submission.student_count), ("mentor", user, 0))

    def test_industry_keeps_the_company_and_academics_their_own_choice(self):
        industry = mentor_body(
            email="ind@example.test", affiliation="industry", company="Cochlear", institution="",
            universityYear="", fieldOfStudy="",
        )
        academic = mentor_body(email="acad@example.test", affiliation="academic", universityYear="")
        self.assertEqual(self.register(industry).status_code, 201)
        self.assertEqual(self.register(academic).status_code, 201)
        ind = MentorProfile.objects.get(user__email="ind@example.test")
        self.assertEqual((ind.background, ind.company, ind.institution, ind.field_of_study), ("industry", "Cochlear", "", ""))
        acad = MentorProfile.objects.get(user__email="acad@example.test")
        self.assertEqual((acad.background, acad.get_background_display()), ("academic", "Academic / research staff"))

    def test_what_the_form_asks_for_is_checked_again_here(self):
        long = " ".join(["word"] * 151)
        cases = {
            "mentor.company": mentor_body(affiliation="industry", company=""),
            "mentor.institution": mentor_body(institution=""),
            "mentor.fieldOfStudy": mentor_body(fieldOfStudy=""),
            "mentor.universityYear": mentor_body(universityYear=""),
            "mentor.state": mentor_body(state=""),
            "mentor.interests": mentor_body(interests=[]),
            "mentor.capacity": mentor_body(capacity="6"),
            "mentor.affiliation": mentor_body(affiliation="retired"),
            "mentor.mentoringApproach": mentor_body(mentoringApproach=long),
            "mentor.availability.0": mentor_body(availability=[{"weekday": "1", "start": "10:00", "end": ""}]),
            "mentor.nickname": mentor_body(nickname="J"),
        }
        for field, body in cases.items():
            with self.subTest(field=field):
                response = self.register(body)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data["fields"] if "fields" in response.data else response.data)
        ends_first = mentor_body(availability=[{"weekday": "1", "start": "10:00", "end": "09:00"}])
        response = self.register(ends_first)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="jordan.ng@uni.example.test").exists())

    def test_closed_dates_an_email_with_an_account_and_a_late_link_are_refused(self):
        User.objects.create_user(email="taken@example.test")
        response = self.register(mentor_body(email="Taken@example.test"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("mentor.email", response.data["fields"] if "fields" in response.data else response.data)

        response = self.register(token=self.mint()["token"])
        self.assertEqual(response.status_code, 400)

        self.close_window()
        response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MentorProfile.objects.exists())

    def test_the_same_request_sent_again_registers_one_mentor(self):
        key = uuid.uuid4()
        first = self.register(key=key)
        again = self.register(key=key)
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertEqual(first.data["reference_code"], again.data["reference_code"])
        self.assertEqual(MentorProfile.objects.count(), 1)

    def test_the_mentor_gets_their_registration_email_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.register()
        [sent] = mail.outbox
        self.assertEqual(sent.to, ["jordan.ng@uni.example.test"])
        self.assertEqual(sent.subject, "BIOTech Futures: Registration")
        html = sent.alternatives[0][0]
        self.assertIn("Hi Jordan,", html)
        self.assertIn("as a mentor", html)
