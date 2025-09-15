from django.contrib import admin
from .models import Users, AdminProfile, AreasOfInterest, Background, MentorProfile, RelationshipType, StudentInterest, StudentProfile, StudentSupervisor, SupervisorProfile

# Register your models here.
admin.site.register(Users)
admin.site.register(AdminProfile)
admin.site.register(AreasOfInterest)
admin.site.register(Background)
admin.site.register(MentorProfile)
admin.site.register(RelationshipType)
admin.site.register(StudentInterest)
admin.site.register(StudentProfile)
admin.site.register(StudentSupervisor)
admin.site.register(SupervisorProfile)
