"""The emails sent once someone registers (System Emails > Registration), as
the client's Power Automate flows sent them. Sent after the registration is
saved, never for one that's rolled back, and each in the background so
registering doesn't wait on the mail server.

So far: a student registering on their own, including with a late link
(``registration_student``); each student registering as a team, or joining a
group by its code (``registration_group``); a supervisor registering
students, to each student (``registration_by_supervisor``) and once to the
supervisor for each registration (``registration_supervisor``), never for an
admin registering them; and a mentor registering (``registration_mentor``).
"""
from __future__ import annotations

from django.conf import settings

from apps.services.system_email import send_system_email
from apps.submissions.services import current_cohort

STUDENT_KEY = "registration_student"
GROUP_KEY = "registration_group"
SUPERVISOR_KEY = "registration_supervisor"
SUPERVISED_KEY = "registration_by_supervisor"
MENTOR_KEY = "registration_mentor"

# Each journey's email, to each person it registered.
STUDENT_EMAILS = {"student_individual": STUDENT_KEY, "student_team": GROUP_KEY, "mentor": MENTOR_KEY}


def registration_context(user) -> dict:
    """The merge values a registration email carries: who it's to, and the
    challenge year they registered for."""
    return {"First_Name": user.first_name, "YEAR": str(current_cohort())}


def supervisor_context(user) -> dict:
    """A supervisor's, with where they see their students: My Students."""
    return {**registration_context(user), "STUDENTS_URL": f"{settings.FRONTEND_BASE_URL}/#/my-students"}


def supervised_context(user, supervisor) -> dict:
    """A student's, registered by ``supervisor``: who registered them."""
    return {**registration_context(user), "SUPERVISOR_NAME": supervisor.get_full_name() or supervisor.email}


def send_registration_emails(journey: str, users, *, supervisor=None) -> None:
    """Each registration email ``journey`` sends, to the people it saved
    (``users``, in their order on the form), and to the ``supervisor`` who
    registered them, if one did."""
    key = STUDENT_EMAILS.get(journey)
    if key:
        for user in users:
            send_system_email(key, user.email, registration_context(user), background=True)
    if supervisor is not None:
        # Each student they registered, then the supervisor.
        for user in users:
            send_system_email(SUPERVISED_KEY, user.email, supervised_context(user, supervisor), background=True)
        send_system_email(SUPERVISOR_KEY, supervisor.email, supervisor_context(supervisor), background=True)
