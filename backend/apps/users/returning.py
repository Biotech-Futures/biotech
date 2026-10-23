"""Coming back for a later year. Start new year (Management > New Year)
deactivates every student, mentor and supervisor, and registering again is
the only way back: a student or mentor registers with the same email as
before, and a supervisor confirms their email with a code on the
registration page, which signs them in to register their students
(``returning_views``). Never an admin's account, nor a suspended one, and a
student or mentor comes back once a year, to an account from an earlier one.
An admin setting a student from an earlier year back to Active on Admin >
Users brings them back the same way (``bring_back_for_this_year``)."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.rbac import is_admin, user_has_role
from apps.common.role_names import ROLE_STUDENT, get_role_by_name

from .models import MentorProfile, RegistrationSubmission, StudentProfile, SupervisorProfile, User


def _admin(user) -> bool:
    return is_admin(user) or user.is_staff or user.is_superuser


def _deactivated(email: str) -> User | None:
    user = (
        User.objects.filter(email__iexact=email, account_status=User.AccountStatus.DEACTIVATED)
        .order_by("pk")
        .first()
    )
    return None if user is None or _admin(user) else user


def returning_student(email: str) -> User | None:
    """The account a student registering with ``email`` comes back to: a
    student's from an earlier challenge year, deactivated. None for anyone
    else, so their email stays taken."""
    from apps.submissions.services import current_cohort

    user = _deactivated(email)
    if user is None:
        return None
    profile = StudentProfile.objects.filter(user=user).only("challenge_year").first()
    if profile is None or profile.challenge_year >= current_cohort():
        return None
    return user


def returning_mentor(email: str, window) -> User | None:
    """The account a mentor registering with ``email`` comes back to: a
    mentor's, deactivated, who hasn't registered in ``window`` (this year's)
    already. None for anyone else."""
    user = _deactivated(email)
    if user is None or not MentorProfile.objects.filter(user=user).exists():
        return None
    if RegistrationSubmission.objects.filter(window=window, student=user).exists():
        return None
    return user


def returning_supervisor(email: str) -> User | None:
    """The supervisor confirming ``email`` on the registration page: one
    Start new year deactivated, or one still active (who's simply signed in).
    None for anyone else, an admin included."""
    user = (
        User.objects.filter(
            email__iexact=email,
            account_status__in=(User.AccountStatus.ACTIVE, User.AccountStatus.DEACTIVATED),
        )
        .order_by("pk")
        .first()
    )
    if user is None or _admin(user) or not SupervisorProfile.objects.filter(user=user).exists():
        return None
    return user


def restart_guardian_permission(profile: StudentProfile, now) -> None:
    """A returning student's guardian gives permission again for the new
    year: the permission, media answer and reminders start again, and any
    consent link still out stops working. Their signed forms stay on record.
    The caller saves ``profile``."""
    profile.has_join_permission = False
    profile.joinperm_responseID = None
    profile.joinperm_granted_at = None
    profile.media_consent = None
    profile.guardian_reminder_sent_at = None
    profile.guardian_reminder_due_at = None
    profile.guardian_details_reminded_on = None
    profile.guardian_details_link_at = None
    profile.clear_pending_guardian()
    profile.consent_requests.filter(used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)


def earlier_challenge_year(profile: StudentProfile | None, year: int) -> int | None:
    """The challenge year a student is from, when it's before ``year`` (the
    one in progress): Admin > Users says so before they're set back to Active."""
    if profile is None or profile.challenge_year >= year:
        return None
    return profile.challenge_year


def bring_back_for_this_year(user: User, now=None) -> bool:
    """A student from an earlier challenge year an admin sets back to Active
    (Admin > Users) is this year's, as registering again would make them: a
    student's role for this year, and their guardian gives permission again,
    emailed the form once it's saved. Whether they were from an earlier year."""
    from apps.resources.models import RoleAssignmentHistory
    from apps.submissions.services import current_cohort

    from .guardian_reminders import email_registered_guardians

    year = current_cohort()
    profile = StudentProfile.objects.filter(user=user, challenge_year__lt=year).first()
    if profile is None:
        return False
    now = now or timezone.now()
    profile.challenge_year = year
    restart_guardian_permission(profile, now)
    profile.save()
    if not user_has_role(user, ROLE_STUDENT):
        RoleAssignmentHistory.objects.create(
            user=user, role=get_role_by_name(ROLE_STUDENT), valid_from=now, valid_to=now + timedelta(weeks=6),
        )
    transaction.on_commit(lambda: email_registered_guardians([user.pk]))
    return True
