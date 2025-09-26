from django.db import models


class Track(models.TextChoices):
    AUS_NSW = "AUS-NSW", "AUS-NSW"
    AUS_QLD = "AUS-QLD", "AUS-QLD"
    AUS_VIC = "AUS-VIC", "AUS-VIC"
    AUS_WA  = "AUS-WA",  "AUS-WA"
    BRA     = "BRA",     "BRA"
    GLOBAL  = "GLOBAL",  "GLOBAL"


class Experience(models.TextChoices):
    UG  = "UG",  "University - Undergraduate"
    PG  = "PG",  "University - Postgraduate"
    HDR = "HDR", "University - HDR"
    AC  = "AC",  "Academic"
    IN  = "IN",  "Industry"


class Interest(models.Model):
    name = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.name


class Student(models.Model):
    first_name = models.CharField(max_length=80)
    last_name  = models.CharField(max_length=80)
    email      = models.EmailField(unique=True)
    #add supervisor_email
    supervisor_email = models.EmailField(blank=True, default="")

    school     = models.CharField(max_length=200, blank=True)
    year_level = models.PositiveSmallIntegerField()  # 9/10/11/12

    country    = models.CharField(max_length=80)     # Store text directly (later mapped to track)
    region     = models.CharField(max_length=80, blank=True)  # NSW/QLD/VIC/WA/...
    #if assined
    preassigned_group = models.CharField(
        max_length=64, blank=True, default="",  # Recommended to have default=""
        help_text="Group Number from spreadsheet (already grouped students)",
    )

    track      = models.CharField(max_length=16, choices=Track.choices, default=Track.GLOBAL)
    interests  = models.ManyToManyField(Interest, blank=True, related_name="students")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.year_level})"


class StudentGroup(models.Model):
    name      = models.CharField(max_length=120)
    track     = models.CharField(max_length=16, choices=Track.choices, default=Track.GLOBAL)
    year_min  = models.PositiveSmallIntegerField(null=True, blank=True)
    year_max  = models.PositiveSmallIntegerField(null=True, blank=True)

    interests = models.ManyToManyField(Interest, blank=True, related_name="groups")
    members   = models.ManyToManyField(Student, blank=True, related_name="groups")
    mentor = models.ForeignKey(
        "Mentor", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="groups"
    )
    def __str__(self):
        return f"{self.name} [{self.track}]"


class Mentor(models.Model):
    first_name = models.CharField(max_length=80)
    last_name  = models.CharField(max_length=80)
    email      = models.EmailField(unique=True)
    is_active  = models.BooleanField(default=True)

    background = models.CharField(max_length=120, blank=True)  # Original background text (for display purposes)


    institution = models.CharField(max_length=200, blank=True)
    country     = models.CharField(max_length=80)
    region      = models.CharField(max_length=80, blank=True)
    track       = models.CharField(max_length=16, choices=Track.choices, default=Track.GLOBAL)

    max_groups  = models.PositiveSmallIntegerField(default=1)
    interests   = models.ManyToManyField(Interest, blank=True, related_name="mentors")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.track}, {self.background})"


class MentorAvailability(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField()  # 0=Mon .. 6=Sun
    start   = models.TimeField()
    end     = models.TimeField()

    class Meta:
        unique_together = ("mentor", "weekday", "start", "end")
