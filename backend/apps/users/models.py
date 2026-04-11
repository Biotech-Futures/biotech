# USER MODELS
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.contrib.auth.models import AbstractUser, BaseUserManager

class AdminProfile(models.Model):
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True) # Changed to CASCADE to delete admin profile if user is deleted

    class Meta:
        db_table = 'admin_profile'
        verbose_name = "Admin Profile"
        verbose_name_plural = "Admin Profiles"

    def __str__(self):
        return str(self.admin)

class AreasOfInterest(models.Model):
    interest_desc = models.CharField(max_length=255)

    class Meta:
        db_table = 'areas_of_interest'
        verbose_name = "Area of Interest"
        verbose_name_plural = "Areas of Interest"

    def __str__(self):
        return self.interest_desc

class MentorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True) # Changed to CASCADE to delete mentor profile if user is deleted
    institution = models.CharField(db_column='Institution', max_length=255)  # Field name made lowercase.
    mentor_reason = models.CharField(max_length=255)
    max_group_count = models.PositiveIntegerField(default=3)
    # Refined schema: geo + matching display (table_statements.sql mentor_profile)
    country = models.ForeignKey(
        "groups.Countries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentor_profiles",
    )
    state = models.ForeignKey(
        "groups.CountryStates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentor_profiles",
    )
    background = models.CharField(max_length=120, blank=True, default="")
    region = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        db_table = 'mentor_profile'
        verbose_name = "Mentor Profile"
        verbose_name_plural = "Mentor Profiles"
        constraints = [
            # Ensure max_group_count is not negative
            models.CheckConstraint(
                condition=Q(max_group_count__gte=0),
                name='mentor_max_group_count_non_negative'
            ),
        ]
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["state"]),
        ]
    
    def __str__(self):
        return f"Mentor: {self.user}"

class StudentInterest(models.Model):
    interest = models.ForeignKey(AreasOfInterest, on_delete=models.CASCADE) # changed to cascade, might need review but i think it reflects what should happen, like if an interest category is deleted it will follow through here
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'student_interest'
        verbose_name = "Student Interest"
        verbose_name_plural = "Student Interests"
        constraints = [
            models.UniqueConstraint(fields=['interest', 'user'], name='pk_student_interest'),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['interest']),
        ]

    def __str__(self):
        return f"{self.user} interested in {self.interest}"
    
class MentorInterest(models.Model):
    mentor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    interest = models.ForeignKey(AreasOfInterest, on_delete=models.CASCADE)

    class Meta:
        db_table = 'mentor_interest'
        verbose_name = "Mentor Interest"
        verbose_name_plural = "Mentor Interests"
        constraints = [
            models.UniqueConstraint(fields=['mentor_user', 'interest'], name='unique_mentor_interest')
        ]
        indexes = [
            models.Index(fields=['mentor_user']),
            models.Index(fields=['interest']),
        ]

class MentorAvailability(models.Model):
    mentor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = 'mentor_availability'
        verbose_name = "Mentor Availability"
        verbose_name_plural = "Mentor Availability"
        constraints = [
            models.UniqueConstraint(
                fields=['mentor_user', 'weekday', 'start_time', 'end_time'],
                name='unique_mentor_availability_slot',
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0) & Q(weekday__lte=6),
                name='mentor_availability_weekday_valid',
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F('start_time')),
                name='mentor_availability_end_after_start',
            ),
        ]
        indexes = [
            models.Index(fields=['mentor_user']),
            models.Index(fields=['weekday']),
        ]
    
    def __str__(self):
        return f"{self.mentor_user} on {self.weekday} from {self.start_time} to {self.end_time}"

class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.BooleanField(default=False) 
    supervisor = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, blank=True, null=True) # made SET NULL to allow student profiles to persist if a supervisor profile is deleted, but might need review if we want to delete the student profile instead
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField(default=False)
    joinperm_responseID = models.CharField(max_length=255, null=True)
    # Refined schema: geo + pre-assignment (table_statements.sql student_profile)
    country = models.ForeignKey(
        "groups.Countries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
    )
    state = models.ForeignKey(
        "groups.CountryStates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
    )
    preassigned_group = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = 'student_profile'
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['supervisor']),
            models.Index(fields=["country"]),
            models.Index(fields=["state"]),
        ]
        constraints = [
        # Ensure first and last names are not empty
        models.CheckConstraint(
            condition=~Q(pg_first_name=''),
            name='student_first_name_not_empty'
        ),
        models.CheckConstraint(
            condition=~Q(pg_last_name=''),
            name='student_last_name_not_empty'
        ),
        # Ensure school_name is not empty
        models.CheckConstraint(
            condition=~Q(school_name=''),
            name='student_school_name_not_empty'
        ),
        # Ensure year level in expected range (9-12)
        models.CheckConstraint(
            condition=Q(year_lvl__in=[str(i) for i in range(9, 13)]),
            name='student_year_lvl_valid'
        ),
        # Ensure has_join_permission is True only if parent_guardian_flag is True
        models.CheckConstraint(
            condition=Q(has_join_permission=False) | Q(parent_guardian_flag=True),
            name='permission_requires_parent_guardian'
        )
        ]

    def __str__(self):
        return str(self.user)


class StudentSupervisor(models.Model):
    student_user = models.ForeignKey('StudentProfile', on_delete=models.CASCADE)
    supervisor_user = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, null=True) # made SET NULL to allow student-supervisor relationships to persist if a supervisor profile is deleted, but might need review if we want to delete the relationship instead

    class Meta:
        db_table = 'student_supervisor'
        verbose_name = "Student Supervisor"
        verbose_name_plural = "Student Supervisors"
        indexes = [
            models.Index(fields=['student_user']),
            models.Index(fields=['supervisor_user']),
        ]

        constraints = [
            # Composite primary key on (student_user, supervisor_user)
            models.UniqueConstraint(fields=['student_user', 'supervisor_user'], name='pk_student_supervisor'),
            # Ensure student_user is not null
            models.CheckConstraint(condition=~Q(student_user=None), name='student_user_not_null'),
            # Ensure supervisor_user is not null - UPDATE: allows supervisor_user to be null or if not null, that they are not the same
            models.CheckConstraint(condition=Q(supervisor_user__isnull=True) | ~Q(student_user=F('supervisor_user')), name='no_self_supervision'),
        ]
    
    def __str__(self):
        return f"{self.student_user} -> {self.supervisor_user}"


class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True) # Changed to CASCADE to delete supervisor profile if user is deleted, but might need review if we want to keep the profile for record purposes
    school_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'supervisor_profile'
        verbose_name = "Supervisor Profile"
        verbose_name_plural = "Supervisor Profiles"

    def __str__(self):
        return str(self.user)
    

# ---- AUTH USER ---- #

class UserManager(BaseUserManager):
    use_in_migrations = True
    
    def create_user(self, *, email: str, password: str = None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        if password:
            extra.setdefault("account_status", User.AccountStatus.ACTIVE)
        else:
            extra.setdefault("account_status", User.AccountStatus.PENDING)
        extra.setdefault("is_active", extra["account_status"] == User.AccountStatus.ACTIVE)
        user = self.model(
            email=email,
            **extra # for is_superuser etc
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password, **extra):
        if not password:
            raise ValueError("Superusers must have a password")
        extra.setdefault("first_name", "")
        extra.setdefault("last_name", "")
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("account_status", User.AccountStatus.ACTIVE)
        extra.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra)



class User(AbstractUser):
    class AccountStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"

    username = None
    email = models.EmailField(unique=True)
    # note first_name and last_name come pre-built in AbstractUser
    first_name = models.CharField(max_length=255, blank=False)
    last_name  = models.CharField(max_length=255, blank=False)
    track = models.ForeignKey('groups.Tracks', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    is_active = models.BooleanField(default=False)
    account_status = models.CharField(
        max_length=50,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    # is_staff is already defined in AbstractUser
    # is_staff   = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["track"]),
            models.Index(fields=["account_status"]),
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        inactive_statuses = {
            self.AccountStatus.INVITED,
            self.AccountStatus.PENDING,
            self.AccountStatus.SUSPENDED,
            self.AccountStatus.DEACTIVATED,
        }

        if update_fields is not None:
            update_fields = set(update_fields)
            if "is_active" in update_fields and "account_status" not in update_fields:
                if self.is_active:
                    self.account_status = self.AccountStatus.ACTIVE
                elif self.account_status == self.AccountStatus.ACTIVE:
                    self.account_status = self.AccountStatus.DEACTIVATED
                update_fields.add("account_status")
            elif "account_status" in update_fields and "is_active" not in update_fields:
                self.is_active = self.account_status == self.AccountStatus.ACTIVE
                update_fields.add("is_active")
            elif self.account_status == self.AccountStatus.ACTIVE:
                self.is_active = True
            elif self.account_status in inactive_statuses:
                self.is_active = False
            kwargs["update_fields"] = list(update_fields)
        else:
            if self.account_status == self.AccountStatus.ACTIVE:
                self.is_active = True
            elif self.is_active:
                self.account_status = self.AccountStatus.ACTIVE
            elif self.account_status in inactive_statuses:
                self.is_active = False
            else:
                self.account_status = self.AccountStatus.DEACTIVATED
        super().save(*args, **kwargs)

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

class AdminScope(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey('groups.Tracks', on_delete=models.CASCADE, null=True, blank=True)
    is_global = models.BooleanField(default=False)

    class Meta:
        db_table = 'admin_scope'
        verbose_name = "Admin Scope"
        verbose_name_plural = "Admin Scopes"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'track'],
                condition=Q(is_global=False),
                name='unique_admin_scope_per_track',
            ),
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_global=True),
                name='unique_global_admin_scope',
            ),
            models.CheckConstraint(
                condition=(Q(is_global=True) & Q(track__isnull=True)) | (Q(is_global=False) & Q(track__isnull=False)),
                name='admin_scope_global_or_track',
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['track']),
        ]

    def __str__(self):
        return f"{self.user} -> {'global' if self.is_global else self.track}"
