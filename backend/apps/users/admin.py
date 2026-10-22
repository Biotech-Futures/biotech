from django.contrib import admin
from .models import User, AdminProfile, AdminScope, AreasOfInterest, EmailVerification, EmailVerificationCredits, KnownUniversity, MentorAvailability, MentorProfile, StudentProfile, StudentSupervisor, SupervisorProfile, UserInterest

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


@admin.register(KnownUniversity)
class KnownUniversityAdmin(admin.ModelAdmin):
    list_display = ("full_name", "acronym", "country", "created_at")
    search_fields = ("full_name", "acronym", "country")


class ReadOnlyAdmin(admin.ModelAdmin):
    """Shown for reference only: these rows are written by the email
    verification service, never by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailVerification)
class EmailVerificationAdmin(ReadOnlyAdmin):
    """Rows can be deleted, so a wrongly stored answer (an "invalid" for a
    mailbox that works, say) is cleared and the address is checked again."""

    list_display = ("email", "status", "reason", "checked_at")
    list_filter = ("status",)
    search_fields = ("email",)

    def has_delete_permission(self, request, obj=None):
        return admin.ModelAdmin.has_delete_permission(self, request, obj)


@admin.register(EmailVerificationCredits)
class EmailVerificationCreditsAdmin(ReadOnlyAdmin):
    list_display = ("remaining", "updated_at", "alerted_thresholds", "lookups_on", "lookups_today")
