"""A mentor registering on the public registration page
(apps.users.mentor_registration): saved as an admin's Import Mentors saves
one, pending until an admin activates them, with their registration email."""
import uuid
from datetime import time

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    MentorProfile, RegistrationSubmission, StudentProfile, SupervisorProfile, User, UserInterest,
)
from apps.users.models.mentor_availability import MentorAvailability
from apps.users.views import REGISTRATION_PER_IP_LIMIT
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
        "weeklyHours": "4",
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
    return {"journey": "mentor", "payload": {"mentor": mentor}, "policiesAgreed": True}


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
             profile.field_of_study, profile.max_group_count, profile.weekly_hours),
            ("postgraduate", "University of Sydney", "", "2", "Bioengineering", 3, 4),
        )
        self.assertEqual(profile.mentor_reason, "I'd like to help students find their way into research.")
        self.assertEqual(profile.relevant_background, "Two years of lab work on tissue scaffolds.")
        self.assertEqual(profile.mentoring_approach, "Weekly check-ins and pointing them to good sources.")
        self.assertEqual(
            sorted(UserInterest.objects.filter(user=user).values_list("interest__interest_desc", flat=True)),
            ["AI & Robotics and Smart Systems", "Biomedical Innovations"],
        )
        # Weekly times the form no longer asks for are still kept when given;
        # the empty row is dropped.
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
        self.assertEqual((acad.background, acad.get_background_display()), ("academic", "Academic"))

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
            "mentor.weeklyHours": mentor_body(weeklyHours="0"),
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

    def test_each_written_answer_is_kept_to_150_words(self):
        long = " ".join(["word"] * 151)
        for field in ("background", "motivation", "mentoringApproach"):
            with self.subTest(field=field):
                response = self.register(mentor_body(**{field: long}))
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(f"mentor.{field}", response.data["fields"] if "fields" in response.data else response.data)
        # Exactly 150 words is allowed.
        response = self.register(mentor_body(background=" ".join(["word"] * 150)))
        self.assertEqual(response.status_code, 201, response.data)

    def test_a_name_and_country_are_needed(self):
        for field in ("firstName", "lastName", "country"):
            left_out = mentor_body()
            del left_out["payload"]["mentor"][field]
            for how, body in (("blank", mentor_body(**{field: ""})), ("left out", left_out)):
                with self.subTest(field=field, how=how):
                    response = self.register(body)
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(f"mentor.{field}", response.data["fields"] if "fields" in response.data else response.data)
        self.assertFalse(MentorProfile.objects.exists())

    def test_hours_per_week_are_needed_and_a_whole_number_up_to_40(self):
        for hours in ("", "41", "2.5"):
            with self.subTest(hours=hours):
                response = self.register(mentor_body(weeklyHours=hours))
                self.assertEqual(response.status_code, 400, response.data)
        body = mentor_body()
        del body["payload"]["mentor"]["weeklyHours"]
        self.assertEqual(self.register(body).status_code, 400)

    def test_a_mentor_agrees_to_the_policies_and_its_time_is_kept(self):
        refused = mentor_body()
        refused["policiesAgreed"] = False
        self.assertEqual(self.register(refused).status_code, 400)

        response = self.register()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(User.objects.get(email="jordan.ng@uni.example.test").policies_agreed_at)

    def test_the_form_without_weekly_times_registers(self):
        body = mentor_body(weeklyHours="40")
        del body["payload"]["mentor"]["availability"]
        response = self.register(body)
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="jordan.ng@uni.example.test")
        self.assertEqual(MentorProfile.objects.get(user=user).weekly_hours, 40)
        self.assertFalse(MentorAvailability.objects.filter(mentor_user=user).exists())

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

    def test_an_email_that_belongs_to_a_student_or_a_supervisor_is_refused(self):
        student = User.objects.create_user(email="pupil@example.test", first_name="Robin", last_name="Existing")
        StudentProfile.objects.create(
            user=student, pg_first_name="Pat", pg_last_name="Parent", school_name="Test High School", year_lvl="10",
        )
        supervisor = User.objects.create_user(email="grace@example.test", first_name="Grace", last_name="Green")
        SupervisorProfile.objects.create(user=supervisor, school_name="Test High School")
        for typed in ("pupil@example.test", "Grace@Example.test"):
            with self.subTest(typed=typed):
                response = self.register(mentor_body(email=typed))
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("mentor.email", response.data["fields"] if "fields" in response.data else response.data)
        # Neither account was given the mentor role or a mentor profile.
        self.assertFalse(MentorProfile.objects.exists())
        self.assertFalse(RoleAssignmentHistory.objects.filter(role__role_name="mentor").exists())

    def test_the_per_ip_limit_applies_but_a_repeated_request_still_gets_its_receipt(self):
        key = uuid.uuid4()
        first = self.register(key=key)
        self.assertEqual(first.status_code, 201, first.data)
        cache.set("registration_ip:127.0.0.1", REGISTRATION_PER_IP_LIMIT)
        response = self.register(mentor_body(email="another@example.test"))
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(email="another@example.test").exists())
        again = self.register(key=key)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data, first.data)

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
