"""The emails sent once someone registers (System Emails > Registration), as
the client's Power Automate flows sent them. Sent after the registration is
saved, never for one that's rolled back, and each in the background so
registering doesn't wait on the mail server.

So far: a student registering on their own, including with a late link
(``registration_student``); and each student registering as a team, or
joining a group by its code (``registration_group``).
"""
from __future__ import annotations

from apps.services.system_email import send_system_email
from apps.submissions.services import current_cohort

STUDENT_KEY = "registration_student"
GROUP_KEY = "registration_group"

# Each journey's email, to each student it registered.
STUDENT_EMAILS = {"student_individual": STUDENT_KEY, "student_team": GROUP_KEY}


def registration_context(user) -> dict:
    """The merge values a registration email carries: who it's to, and the
    challenge year they registered for."""
    return {"First_Name": user.first_name, "YEAR": str(current_cohort())}


def send_registration_emails(journey: str, users) -> None:
    """Each registration email ``journey`` sends, to the people it saved
    (``users``, in their order on the form)."""
    key = STUDENT_EMAILS.get(journey)
    if key:
        for user in users:
            send_system_email(key, user.email, registration_context(user), background=True)
