from django.contrib import admin
from .models import User, AdminProfile, AdminScope, AreasOfInterest, MentorAvailability, MentorProfile, StudentProfile, StudentSupervisor, SupervisorProfile, UserInterest

# Register your models here.
admin.site.register(User)
admin.site.register(AdminProfile)
admin.site.register(AdminScope)
admin.site.register(AreasOfInterest)
admin.site.register(MentorAvailability)
admin.site.register(UserInterest)
admin.site.register(MentorProfile)
admin.site.register(StudentProfile)
admin.site.register(StudentSupervisor)
admin.site.register(SupervisorProfile)
