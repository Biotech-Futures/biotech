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
        

class Background(models.Model):
    background_desc_unique_field = models.TextField() 
    class Meta:
        db_table = 'background'
        verbose_name = "Background"
        verbose_name_plural = "Backgrounds"

    def __str__(self):
        return self.background_desc_unique_field

class MentorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True) # Changed to CASCADE to delete mentor profile if user is deleted
    background = models.ForeignKey(Background, on_delete=models.PROTECT)
    institution = models.CharField(db_column='Institution', max_length=255)  # Field name made lowercase.
    mentor_reason = models.CharField(max_length=255)
    max_grp_cnt = models.IntegerField()

    class Meta:
        db_table = 'mentor_profile'
        verbose_name = "Mentor Profile"
        verbose_name_plural = "Mentor Profiles"
        constraints = [
            # Ensure max_grp_cnt is not negative
            models.CheckConstraint(
                condition=Q(max_grp_cnt__gte=0),
                name='mentor_max_grp_non_negative'
            ),
        ]
    
    def __str__(self):
        return f"Mentor: {self.user}"


class RelationshipType(models.Model):
    relationship_type_id = models.BigAutoField(primary_key=True)
    relationship_type = models.CharField(unique=True, max_length=255)

    class Meta:
        db_table = 'relationship_type'
        verbose_name = "Relationship Type"
        verbose_name_plural = "Relationship Types"

    def __str__(self):
        return self.relationship_type




class StudentInterest(models.Model):
    interest = models.ForeignKey(AreasOfInterest, on_delete=models.CASCADE) # changed to cascade, might need review but i think it reflects what should happen, like if an interest category is deleted it will follow through here
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'student_interest'
        verbose_name = "Student Interest"
        verbose_name_plural = "Student Interests"
        constraints = [
            models.UniqueConstraint(fields=['interest', 'user'], name='pk_student_interest')
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['interest']),
        ]

    def __str__(self):
        return f"{self.user} interested in {self.interest}"


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    pg_first_name = models.CharField(max_length=255)
    pg_last_name = models.CharField(max_length=255)
    parent_guardian_flag = models.BooleanField(default=False) 
    supervisor = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, blank=True, null=True) # made SET NULL to allow student profiles to persist if a supervisor profile is deleted, but might need review if we want to delete the student profile instead
    interest = models.ForeignKey(AreasOfInterest, on_delete=models.SET_NULL, blank=True, null=True) # made SET NULL to allow student profiles to persist if an interest category is deleted, but might need review if we want to delete the profile instead
    school_name = models.CharField(max_length=255)
    year_lvl = models.CharField(max_length=255)
    has_join_permission = models.BooleanField(default=False)
    joinperm_responseID = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = 'student_profile'
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['supervisor']),
            models.Index(fields=['interest']),
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
    relationship_type = models.ForeignKey('RelationshipType', on_delete=models.PROTECT)

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
            # Ensure relationship_type is not null
            models.CheckConstraint(condition=~Q(relationship_type=None), name='relationship_type_not_null'),
            # Ensure student_user is not null
            models.CheckConstraint(condition=~Q(student_user=None), name='student_user_not_null'),
            # Ensure supervisor_user is not null - UPDATE: allows supervisor_user to be null or if not null, that they are not the same
            models.CheckConstraint(condition=Q(supervisor_user__isnull=True) | ~Q(student_user=F('supervisor_user')), name='no_self_supervision'),
        ]
    
    def __str__(self):
        return f"{self.student_user} -> {self.supervisor_user} ({self.relationship_type})"


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
        return self.create_user(email=email, password=password, **extra)



class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    # note first_name and last_name come pre-built in AbstractUser
    first_name = models.CharField(max_length=255, blank=False)
    last_name  = models.CharField(max_length=255, blank=False)
    track = models.ForeignKey('groups.Tracks', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    state = models.ForeignKey('groups.CountryStates', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='users')
    status = models.BooleanField(default=False)
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
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

# class Users(models.Model):
#     first_name = models.CharField(max_length=255)
#     last_name = models.CharField(max_length=255)
#     email = models.CharField(max_length=255, unique=True)
#     status = models.BooleanField(default=False)
#     track = models.ForeignKey('groups.Tracks', on_delete=models.PROTECT)
#     state = models.ForeignKey('groups.CountryStates', on_delete=models.PROTECT)

#     class Meta:
#         db_table = 'users'
#         verbose_name = "User"
#         verbose_name_plural = "Users"
#         indexes = [
#             models.Index(fields=['track']),
#             models.Index(fields=['state']),
#         ]

#     def __str__(self):
#         return f"{self.first_name} {self.last_name}"

