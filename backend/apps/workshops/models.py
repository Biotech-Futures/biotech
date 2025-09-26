# WORKSHOPS MODELS
from django.conf import settings
from django.db import models

class WorkshopAttendance(models.Model):
    workshop = models.ForeignKey('Workshops', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    responded = models.BooleanField(default=False)

    class Meta:
        db_table = 'workshop_attendance'
        constraints = [
            models.UniqueConstraint(fields=['workshop', 'user'], name='pk_workshop_attendance')
        ]
        verbose_name = "Workshop Attendance"
        verbose_name_plural = "Workshop Attendances"

    def __str__(self):
        return f"{self.user} allocated {self.workshop}"

class Workshops(models.Model):
    workshop_id = models.BigAutoField(primary_key=True)
    workshop_name = models.CharField(max_length=255)
    start_datetime = models.DateTimeField()
    duration = models.DurationField()
    location = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    zoom_link = models.CharField(max_length=255, blank=True, null=True)
    host_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    group = models.ForeignKey('groups.Groups', on_delete=models.PROTECT)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'workshops'
        verbose_name = "Workshop"
        verbose_name_plural = "Workshops"
        indexes = [
            models.Index(fields=['start_datetime']),
            models.Index(fields=['group']),
            models.Index(fields=['host_user'])
        ]

    def __str__(self):
        return f"{self.workshop_name} ({self.start_datetime})"