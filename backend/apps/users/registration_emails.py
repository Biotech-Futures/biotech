"""The emails sent once someone registers (System Emails > Registration), as
the client's Power Automate flows sent them. Sent after the registration is
saved, never for one that's rolled back, and each in the background so
registering doesn't wait on the mail server.

So far: a student registering on their own, including with a late link
(``registration_student``); each student registering as a team, or joining a
group by its code (``registration_group``); a supervisor registering
students, to each student (``registration_by_supervisor``) and once to the
supervisor for each registration (``registration_supervisor``); an admin
registering students, to each student, naming the supervisor the admin chose
(``registration_by_admin``); a mentor registering (``registration_mentor``);
a supervisor registering themselves (``registration_new_supervisor``); and a
supervisor a student names, when their account was created for them
(``registration_named_supervisor``).
"""
from __future__ import annotations

from django.conf import settings

from apps.services.system_email import send_system_email
from apps.submissions.services import current_cohort

STUDENT_KEY = "registration_student"
GROUP_KEY = "registration_group"
SUPERVISOR_KEY = "registration_supervisor"
SUPERVISED_KEY = "registration_by_supervisor"
ADMIN_KEY = "registration_by_admin"
MENTOR_KEY = "registration_mentor"
NEW_SUPERVISOR_KEY = "registration_new_supervisor"
NAMED_SUPERVISOR_KEY = "registration_named_supervisor"

# Each journey's email, to each person it registered.
STUDENT_EMAILS = {
    "student_individual": STUDENT_KEY, "student_team": GROUP_KEY, "mentor": MENTOR_KEY,
    "supervisor": NEW_SUPERVISOR_KEY,
}


def registration_context(user) -> dict:
    """The merge values a registration email carries: who it's to, and the
    challenge year they registered for."""
    return {"First_Name": user.first_name, "YEAR": str(current_cohort())}


def supervisor_context(user) -> dict:
    """A supervisor's, with where they see their students: My Students."""
    return {**registration_context(user), "STUDENTS_URL": f"{settings.FRONTEND_BASE_URL}/#/my-students"}


def names_text(users) -> str:
    """Their names, as a sentence says them: "A", "A and B", "A, B and C"."""
    names = [user.get_full_name() or user.email for user in users]
    return " and ".join(names) if len(names) < 3 else f"{', '.join(names[:-1])} and {names[-1]}"


def named_supervisor_context(supervisor, students) -> dict:
    """A supervisor's a student named: who named them, and My Students."""
    return {**supervisor_context(supervisor), "STUDENT_NAMES": names_text(students)}


def send_named_supervisor_email(supervisor, students) -> None:
    """To the supervisor ``students`` named registering, whose account was
    created for them (``registration_intake.create_nominated_supervisor``)."""
    send_system_email(
        NAMED_SUPERVISOR_KEY, supervisor.email, named_supervisor_context(supervisor, students), background=True,
    )


def supervised_context(user, supervisor) -> dict:
    """A student's, registered by ``supervisor``: who registered them."""
    return {**registration_context(user), "SUPERVISOR_NAME": supervisor.get_full_name() or supervisor.email}


def send_registration_emails(journey: str, users, *, supervisor=None, admin_for=None, group=None) -> None:
    """Each registration email ``journey`` sends, to the people it saved
    (``users``, in their order on the form), and to the ``supervisor`` who
    registered them, if one did. ``admin_for``: an admin registered them,
    for the supervisor of that name. ``group``: the group they made or
    joined, whose code a student group's email carries.

    A student someone else registered (a team's students after the one who
    sent the form, and every student a supervisor or an admin registers) is
    sent, while they have no password, a link to set one (SET_PASSWORD_URL)."""
    from .registration_password import emailed_password_url

    if journey == "student_team":
        by_others = users[1:]
    elif supervisor is not None or admin_for is not None:
        by_others = users
    else:
        by_others = []
    links = {user.pk: emailed_password_url(user) for user in by_others if not user.has_usable_password()}

    def with_link(user, context: dict) -> dict:
        return {**context, "SET_PASSWORD_URL": links[user.pk]} if user.pk in links else context

    key = STUDENT_EMAILS.get(journey)
    if key:
        for user in users:
            context = registration_context(user)
            if key == GROUP_KEY and group is not None and group.code:
                context["GROUP_CODE"] = group.code
            send_system_email(key, user.email, with_link(user, context), background=True)
    if supervisor is not None:
        # Each student they registered, then the supervisor.
        for user in users:
            context = with_link(user, supervised_context(user, supervisor))
            send_system_email(SUPERVISED_KEY, user.email, context, background=True)
        send_system_email(SUPERVISOR_KEY, supervisor.email, supervisor_context(supervisor), background=True)
    if admin_for is not None:
        for user in users:
            context = with_link(user, {**registration_context(user), "SUPERVISOR_NAME": admin_for})
            send_system_email(ADMIN_KEY, user.email, context, background=True)
