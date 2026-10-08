from django.conf import settings
from django.db import models
from django.db.models import Q

class StudentProfile(models.Model):
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

    class Meta:
        db_table = 'student_profile'
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['supervisor']),
        ]
        constraints = [
        models.CheckConstraint(
            condition=~Q(pg_first_name=''),
            name='student_first_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(pg_last_name=''),
            name='student_last_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(school_name=''),
            name='student_school_name_not_empty'
        ),
        models.CheckConstraint(
            condition=Q(year_lvl__in=[str(i) for i in range(9, 13)]),
            name='student_year_lvl_valid'
        ),
        models.CheckConstraint(
            condition=Q(has_join_permission=False) | Q(parent_guardian_flag=True),
            name='permission_requires_parent_guardian'
        )
        ]

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
