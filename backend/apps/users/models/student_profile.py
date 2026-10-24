from django.conf import settings
from django.db import models
from django.db.models import Q


def default_challenge_year() -> int:
    """The challenge year a student is added in."""
    from apps.submissions.services import current_cohort  # its models import this app

    return current_cohort()


class StudentProfile(models.Model):
    class RegisteredBy(models.TextChoices):
        SELF = "self", "The student"
        PEER = "peer", "Another student"
        SUPERVISOR = "supervisor", "Their supervisor"
        ADMIN = "admin", "An admin"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    pg_email = models.EmailField(blank=True, null=True)
    parent_guardian_flag = models.BooleanField(default=False) 
    supervisor = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, blank=True, null=True)
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField(default=False)
    joinperm_responseID = models.CharField(max_length=255, null=True)
    joinperm_granted_at = models.DateTimeField(blank=True, null=True)
    guardian_reminder_sent_at = models.DateTimeField(blank=True, null=True)
    guardian_reminder_due_at = models.DateTimeField(blank=True, null=True)
    # A guardian change the student asked for after consent was received. The
    # consenting guardian stays on file until the new one consents, at which
    # point the join-permission webhook promotes these into pg_*.
    pending_pg_first_name = models.CharField(max_length=255, blank=True, default="")
    pending_pg_last_name = models.CharField(max_length=255, blank=True, default="")
    pending_pg_email = models.EmailField(blank=True, null=True)
    pending_pg_requested_at = models.DateTimeField(blank=True, null=True)
    # The guardian's answer on the consent form: may the participant be
    # photographed/recorded and so attend in-person events. None when consent
    # came through the old Qualtrics form, which didn't send the answer here.
    media_consent = models.BooleanField(blank=True, null=True)
    # The last day the student was emailed to add their parent/guardian's
    # details (apps.users.guardian_details), so a rerun never emails twice.
    guardian_details_reminded_on = models.DateField(blank=True, null=True)
    # When a supervisor last copied the guardian-details form link: every copy
    # out works until FORM_LINK_LIFETIME after the latest.
    guardian_details_link_at = models.DateTimeField(blank=True, null=True)
    # Who registered the student; blank for those registered before it was
    # recorded. Registered by a supervisor, or edited by one since, the student
    # can't change their own details: they ask their supervisor (``details_locked``).
    registered_by = models.CharField(max_length=16, choices=RegisteredBy.choices, blank=True, default="")
    supervisor_edited_at = models.DateTimeField(blank=True, null=True)
    # The challenge year they're taking part in: the one they registered in,
    # or came back for by registering again once Start new year deactivated
    # them (apps.users.returning). Guardian Permission's tables and the
    # guardian and supervisor emails count this year's students by it.
    challenge_year = models.PositiveSmallIntegerField(default=default_challenge_year)

    class Meta:
        db_table = 'student_profile'
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['supervisor']),
            models.Index(fields=['challenge_year']),
        ]
        constraints = [
        # A guardian may be left for later when someone else registered the
        # student: a peer, their supervisor, or an admin (Management > Registration).
        models.CheckConstraint(
            condition=~Q(pg_first_name='') | Q(
                registered_by__in=['peer', 'supervisor', 'admin'], parent_guardian_flag=False,
            ),
            name='student_first_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(pg_last_name='') | Q(
                registered_by__in=['peer', 'supervisor', 'admin'], parent_guardian_flag=False,
            ),
            name='student_last_name_not_empty'
        ),
        # A student a peer registered, or an admin added, may have no school
        # or year yet: an admin may add them before they're known.
        models.CheckConstraint(
            condition=~Q(school_name='') | Q(registered_by__in=['peer', 'admin']),
            name='student_school_name_not_empty'
        ),
        models.CheckConstraint(
            condition=Q(year_lvl__in=[str(i) for i in range(9, 13)])
            | Q(registered_by__in=['peer', 'admin'], year_lvl=''),
            name='student_year_lvl_valid'
        ),
        models.CheckConstraint(
            condition=Q(has_join_permission=False) | Q(parent_guardian_flag=True),
            name='permission_requires_parent_guardian'
        )
        ]

    @property
    def details_locked(self) -> bool:
        """The student's own details are their supervisor's to change: they
        registered the student, or have edited them since. Guardian details
        stay the student's to change until permission is given
        (``guardian_locked``)."""
        return self.registered_by == self.RegisteredBy.SUPERVISOR or self.supervisor_edited_at is not None

    @property
    def guardian_locked(self) -> bool:
        """A student their supervisor manages (``details_locked``) can't change
        their guardian once that guardian has given permission: they contact
        BIOTech Support. While permission is pending, they still can."""
        return self.details_locked and bool(self.has_join_permission)

    @property
    def has_pending_guardian(self):
        return self.pending_pg_requested_at is not None

    def clear_pending_guardian(self):
        self.pending_pg_first_name = ""
        self.pending_pg_last_name = ""
        self.pending_pg_email = None
        self.pending_pg_requested_at = None

    def promote_pending_guardian(self):
        """Make the requested guardian the guardian on file. Consent from them
        replaces the old guardian's, so the caller sets the new consent's date."""
        self.pg_first_name = self.pending_pg_first_name
        self.pg_last_name = self.pending_pg_last_name
        self.pg_email = self.pending_pg_email
        self.parent_guardian_flag = True
        self.clear_pending_guardian()

    def __str__(self):
        return str(self.user)
