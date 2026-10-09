"""Who a System Emails test is "of": each email's real recipients, named as
the page's "of" list shows them, and the merge values that recipient's own
email carries. An email for a whole group lists groups ("BTF01"). An email to
people lists only the roles it goes to: students by this year's groups
("(BTF01) Pat Lee"), mentors with their role too ("(BTF01, mentor) Aga
Smith"), guardians by their student ("(BTF01, guardian) Pat Lee"), and
supervisors and admins by their role alone ("(supervisor) Sam Lee", "(admin)
Ada Lin"). A student or mentor with no group this year shows as "NoGroup"
("(NoGroup) Pat Lee", "(NoGroup, mentor) Aga Smith").

Only what is the recipient's own is filled in. Codes and links that act for
someone (a login code, a password reset link, a guardian's consent link) stay
the registry's samples, so a test can never sign anyone in or record consent,
and so do details that aren't about the person (an event, unread counts). An
email with nothing of a person's own, like the announcement notification, has
no list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from django.conf import settings
from django.db.models import Q

from apps.grading.services.text import natural_key
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.management.services.send_guard import person_name
from apps.users.models import StudentProfile, User

_ROLES = GroupMembership.MembershipRoleChoices
_ADMIN = "admin"
# Where a student or mentor with no group this year shows.
_NO_GROUP = "NoGroup"
# Roles shown without groups, listed after students and mentors in this order.
_ROLE_ONLY = (_ROLES.SUPERVISOR, _ADMIN)
# Accounts the platform no longer emails.
_GONE = (User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED)


class RecipientError(ValueError):
    """A recipient that isn't on the email's list."""


def _this_year():
    from apps.submissions.services import current_cohort

    return current_cohort()


def _person_option(user, role: str, groups=()) -> dict:
    """"(BTF01) Pat Lee" for a student, "(BTF01, mentor) Aga Smith" for a
    mentor, "(BTF01, guardian) Pat Lee" for Pat's guardian, "(supervisor) Sam
    Lee" for a supervisor and "(admin) Ada Lin" for an admin. With no group,
    "(NoGroup) Pat Lee" and "(NoGroup, mentor) Aga Smith". Those in groups
    come first in group order, then those with none, then supervisors, then
    admins."""
    name = person_name(user)
    if role in _ROLE_ONLY:
        return {
            "value": str(user.id),
            "label": f"({role}) {name}",
            "order": (2 + _ROLE_ONLY.index(role), (), name.lower()),
        }
    groups = sorted(groups, key=natural_key) or [_NO_GROUP]
    parts = groups + ([] if role == _ROLES.STUDENT else [role])
    return {
        "value": str(user.id),
        "label": f"({', '.join(parts)}) {name}",
        "order": (1, (), name.lower()) if groups == [_NO_GROUP] else (0, natural_key(groups[0]), name.lower()),
    }


def _sorted(options: list[dict]) -> list[dict]:
    options.sort(key=lambda option: option["order"])
    for option in options:
        del option["order"]
    return options


def _this_years_members(*roles):
    return (
        GroupMembership.objects.filter(
            left_at__isnull=True, group__deleted_at__isnull=True, group__year=_this_year(),
            membership_role__in=roles,
        )
        .exclude(user__email="")
        .exclude(user__account_status__in=_GONE)
        .select_related("user", "group")
    )


def _supervisors():
    """Everyone with the supervisor role, or a supervisor in one of this
    year's groups."""
    from apps.common.rbac import users_with_role
    from apps.common.role_names import ROLE_SUPERVISOR

    in_groups = _this_years_members(_ROLES.SUPERVISOR).values("user_id")
    return (
        User.objects.filter(Q(id__in=users_with_role(ROLE_SUPERVISOR)) | Q(id__in=in_groups))
        .exclude(email="")
        .exclude(account_status__in=_GONE)
    )


def _without_group(role: str):
    """Mentors, and this year's students, with no place in this year's groups."""
    from apps.common.rbac import users_with_role

    in_groups = GroupMembership.objects.filter(
        left_at__isnull=True, group__deleted_at__isnull=True, group__year=_this_year(),
    ).values("user_id")
    users = users_with_role(role).exclude(email="").exclude(account_status__in=_GONE).exclude(id__in=in_groups)
    if role == _ROLES.STUDENT:
        # Last year's students aren't this year's.
        users = users.filter(date_joined__year=_this_year())
    return users


def _admins():
    from apps.common.rbac import users_with_role
    from apps.common.role_names import ROLE_ADMIN

    return users_with_role(ROLE_ADMIN).exclude(email="").exclude(account_status__in=_GONE)


def _people(*roles: str, without_group: bool = True) -> list[dict]:
    """This year's people in ``roles``, once each: students and mentors by
    their groups (a mentor in any group is listed as a mentor), or as
    "NoGroup" with none unless ``without_group`` is False, and supervisors
    and admins by their role alone. Someone with more than one role keeps
    the first: their group, else mentor, else student, else supervisor, else
    admin."""
    people: dict[int, tuple] = {}
    for membership in _this_years_members(*(role for role in roles if role not in _ROLE_ONLY)):
        user, groups, member_roles = people.setdefault(membership.user_id, (membership.user, set(), set()))
        groups.add(membership.group.group_name)
        member_roles.add(membership.membership_role)
    options = [
        _person_option(user, _ROLES.MENTOR if _ROLES.MENTOR in member_roles else _ROLES.STUDENT, groups)
        for user, groups, member_roles in people.values()
    ]
    listed = set(people)
    if without_group:
        for role in (_ROLES.MENTOR, _ROLES.STUDENT):
            if role not in roles:
                continue
            for user in _without_group(role):
                if user.id not in listed:
                    listed.add(user.id)
                    options.append(_person_option(user, role))
    for role, users in ((_ROLES.SUPERVISOR, _supervisors), (_ADMIN, _admins)):
        if role not in roles:
            continue
        for user in users():
            if user.id not in listed:
                listed.add(user.id)
                options.append(_person_option(user, role))
    return _sorted(options)


def _groups(groups) -> list[dict]:
    return [
        {"value": str(group.id), "label": group.group_name}
        for group in sorted(groups, key=lambda group: natural_key(group.group_name))
    ]


def _user(value: str) -> User:
    return User.objects.get(id=int(value))


def _group(value: str) -> Groups:
    return Groups.objects.get(id=int(value))


# --- people ----------------------------------------------------------------------


def _first_name(value: str) -> dict:
    return {"First_Name": _user(value).first_name}


def _everyone() -> list[dict]:
    # Everyone who can sign in or RSVP to an event.
    return _people(_ROLES.STUDENT, _ROLES.MENTOR, _ROLES.SUPERVISOR, _ADMIN)


def _students_and_mentors() -> list[dict]:
    # Group chat members, so nobody without a group; the digest leaves supervisors out.
    return _people(_ROLES.STUDENT, _ROLES.MENTOR, without_group=False)


def _students() -> list[dict]:
    return _people(_ROLES.STUDENT)


def _guardian_details_context(value: str) -> dict:
    from apps.users.guardian_details import details_link

    return {"STUDENT_FIRST_NAME": _user(value).first_name or "", "DETAILS_URL": details_link()}


def _guardian(profile: StudentProfile):
    """The guardian a student's consent email goes to: the one still to ask,
    else the one on file."""
    from apps.users.guardian_consent import Guardian, guardian_to_ask

    return guardian_to_ask(profile) or Guardian(
        profile.pg_first_name, profile.pg_last_name, (profile.pg_email or "").strip().lower(), False,
    )


def _guardian_of(value: str):
    """The student's profile and their guardian; (None, None) without a profile."""
    profile = StudentProfile.objects.select_related("user").filter(user_id=int(value)).first()
    return (profile, _guardian(profile)) if profile else (None, None)


def _guardians() -> list[dict]:
    """Each student's guardian, named by their student: "(BTF01, guardian)
    Pat Lee" is Pat's guardian, and "(NoGroup, guardian) Pat Lee" when Pat
    has no group. A guardian with no email can't be sent it, so isn't
    listed."""
    students: dict[int, set] = {}
    for membership in _this_years_members(_ROLES.STUDENT):
        students.setdefault(membership.user_id, set()).add(membership.group.group_name)
    for user in _without_group(_ROLES.STUDENT):
        students.setdefault(user.id, set())
    options = []
    for profile in StudentProfile.objects.filter(user_id__in=list(students)).select_related("user"):
        if _guardian(profile).email:
            options.append(_person_option(profile.user, "guardian", students[profile.user_id]))
    return _sorted(options)


def _student_notice_context(value: str) -> dict:
    profile, guardian = _guardian_of(value)
    context = {"STUDENT_FIRST_NAME": _user(value).first_name or ""}
    if guardian and guardian.email:
        context["GUARDIAN_EMAIL"] = guardian.email
    return context


def _consent_request_context(value: str) -> dict:
    from apps.users.guardian_consent import is_placeholder_name, student_name

    # CONSENT_URL stays the sample: a real link would let the test record consent.
    profile, guardian = _guardian_of(value)
    user = _user(value)
    if profile is None:
        return {"STUDENT_FIRST_NAME": user.first_name or "", "STUDENT_NAME": person_name(user)}
    first = guardian.first_name or ""
    return {
        "GUARDIAN_FIRST_NAME": "" if is_placeholder_name(first, guardian.last_name, profile) else first,
        "STUDENT_FIRST_NAME": user.first_name or "",
        "STUDENT_NAME": student_name(profile),
    }


# --- groups ----------------------------------------------------------------------


def _this_years_teams():
    return Groups.objects.filter(deleted_at__isnull=True, year=_this_year())


def _submission_url(group: Groups) -> str:
    # Blank without a frontend URL, as the real email has it.
    base = getattr(settings, "FRONTEND_BASE_URL", "")
    return f"{base}/#/submission/{group.id}" if base else ""


def _submission_context(group: Groups, required: list, optional: list) -> dict:
    from apps.submissions.emails import components_list_html
    from apps.submissions.reminders import _format_deadline
    from apps.submissions.services import deadline_for_group

    return {
        "GROUP_NAME": group.group_name,
        "YEAR": _this_year(),
        "REQUIRED_COMPONENTS": required,
        "OPTIONAL_COMPONENTS": optional,
        "REQUIRED_COMPONENTS_LIST": components_list_html(required),
        "OPTIONAL_COMPONENTS_LIST": components_list_html(optional),
        "INCOMPLETE": any(not item["submitted"] for item in required),
        "DEADLINE": _format_deadline(deadline_for_group(group.id).closes_at),
        "SUBMISSION_URL": _submission_url(group),
    }


def _submitted_teams() -> list[dict]:
    return _groups(_this_years_teams().filter(submission__submitted_at__isnull=False))


def _confirmation_context(value: str) -> dict:
    from apps.submissions.emails import build_components

    group = _group(value)
    submission = group.submission
    return {
        **_submission_context(group, *build_components(submission)),
        "SUBMITTED_BY": submission.submitted_by,
    }


def _unsubmitted_teams() -> list[dict]:
    # Reminders go until a team submits.
    return _groups(_this_years_teams().exclude(submission__submitted_at__isnull=False))


def _reminder_context(value: str) -> dict:
    from apps.submissions.reminders import _submission_of, components_for

    group = _group(value)
    return _submission_context(group, *components_for(_submission_of(group)))


def _finalist_teams() -> list[dict]:
    return _groups(Groups.objects.filter(deleted_at__isnull=True, finalist_flag__isnull=False))


def _finalist_context(value: str) -> dict:
    from apps.management.models import FinalistEmailSettings
    from apps.management.services.finalist_notify import finalist_email_context

    return finalist_email_context(_group(value).group_name, FinalistEmailSettings.load())


def _symposium(email_name: str) -> tuple:
    def options() -> list[dict]:
        from apps.management.services import symposium_emails

        return _groups(symposium_emails.audience(getattr(symposium_emails, email_name)).teams)

    def context(value: str) -> dict:
        from apps.management.models import FinalistEmailSettings
        from apps.management.services.symposium_emails import email_context

        return email_context(_group(value).group_name, FinalistEmailSettings.load())

    return options, context


def _results_teams() -> list[dict]:
    from apps.management.services.results_notify import results_audience

    return _groups(results_audience().teams)


def _results_team_files(value: str) -> list[str]:
    """The names of the files the group's email carries (they aren't made)."""
    from apps.management.services import results_notify

    audience = results_notify.results_audience()
    team = next((team for team in audience.teams if str(team.id) == value), None)
    if team is None:
        return []
    return [file.name for file in results_notify.team_files(results_notify.Documents(audience.year), audience, team)]


def _results_team_context(value: str) -> dict:
    from apps.management.models import ResultsEmailSettings
    from apps.management.services.results_notify import results_audience, team_email_context

    return team_email_context(_group(value).group_name, ResultsEmailSettings.load(), results_audience().year)


def _results_supervisors() -> list[dict]:
    """Supervisors due the results email."""
    from apps.management.services.results_notify import results_audience

    return _sorted([
        _person_option(supervisor, _ROLES.SUPERVISOR) for supervisor in results_audience().supervisors
    ])


def _results_supervisor_files(value: str) -> list[str]:
    """The names of the files the supervisor's email carries (they aren't made)."""
    from apps.management.services import results_notify

    audience = results_notify.results_audience()
    supervisor = next((supervisor for supervisor in audience.supervisors if str(supervisor.id) == value), None)
    if supervisor is None:
        return []
    docs = results_notify.Documents(audience.year)
    return [file.name for file in results_notify.supervisor_files(docs, audience, supervisor)]


def _results_supervisor_context(value: str) -> dict:
    from apps.management.services.results_notify import results_audience, supervisor_email_context

    return supervisor_email_context(person_name(_user(value)), results_audience().year)


# --- each email ------------------------------------------------------------------


@dataclass(frozen=True)
class Recipients:
    """An email's "of" list, and the merge values a recipient's email carries."""

    options: Callable[[], list[dict]]
    context: Callable[[str], dict]
    # The names of the files a recipient's email carries, for an email with any.
    files: Optional[Callable[[str], list[str]]] = None


_EVERYONE = Recipients(_everyone, _first_name)

RECIPIENTS: dict[str, Recipients] = {
    "login_code": _EVERYONE,
    "password_reset": _EVERYONE,
    "password_changed": _EVERYONE,
    "unread_messages": Recipients(_students_and_mentors, _first_name),
    "rsvp_reminder": _EVERYONE,
    "event_promotion": _EVERYONE,
    "guardian_details_request": Recipients(_students, _guardian_details_context),
    "guardian_consent_student_notice": Recipients(_students, _student_notice_context),
    "guardian_consent_request": Recipients(_guardians, _consent_request_context),
    "submission_confirmation": Recipients(_submitted_teams, _confirmation_context),
    "submission_reminder": Recipients(_unsubmitted_teams, _reminder_context),
    "finalist_notification": Recipients(_finalist_teams, _finalist_context),
    "nonfinalist_invitation": Recipients(*_symposium("NONFINALIST")),
    "nonsubmission_notice": Recipients(*_symposium("NONSUBMISSION")),
    "results_team": Recipients(_results_teams, _results_team_context, _results_team_files),
    "results_supervisor": Recipients(_results_supervisors, _results_supervisor_context, _results_supervisor_files),
}


def recipient_options(key: str) -> Optional[list[dict]]:
    """The email's "of" list, or None when it has nothing of a person's own."""
    recipients = RECIPIENTS.get(key)
    return recipients.options() if recipients else None


def recipient_context(key: str, value: str) -> dict:
    """The merge values ``value``'s own email carries. Raises RecipientError
    when they aren't on the email's list."""
    recipients = RECIPIENTS.get(key)
    if recipients is None or value not in {option["value"] for option in recipients.options()}:
        raise RecipientError("Pick one from the list.")
    return recipients.context(value)


def recipient_files(key: str, value: str) -> list[str]:
    """The names of the files ``value``'s own email carries; none for most
    emails. ``value`` is one already checked by ``recipient_context``."""
    recipients = RECIPIENTS.get(key)
    return recipients.files(value) if recipients and recipients.files else []
