from django.urls import path
from .profile_options import StudentProfileOptionsView, GuardianInvitationView
from .consent_views import GuardianConsentView, GuardianDetailsFormView
from .guardian_details_views import (
    SendGuardianConsentRemindersView,
    SendGuardianDetailsRemindersView,
    SendSupervisorRegistrationStatusView,
)
from .supervisor_group_views import (
    SupervisedGroupDetailView,
    SupervisedGroupMembersView,
    SupervisedGroupOrderView,
    SupervisedGroupsPlaceView,
    SupervisedGroupsView,
    SupervisedInterestCatalogView,
    SupervisedMentorsView,
)
from .views import (
    UserListHTMLView,
    UsersRetrieveUpdateView,
    MeGuardianView,
    MeRetrieveView,
    ReceiveJoinPermissionView,
    AdminOperationalSummaryView,
    BulkUserStatusView,
    PasswordLoginView,
    SetPasswordView,
    ProfileImageUploadView,
    SupervisedStudentConsentLinksView,
    SupervisedGuardianUploadView,
    SupervisedStudentDetailsLinksView,
    SupervisedStudentDetailView,
    SupervisedStudentEmailView,
    SupervisedStudentOptionsView,
    SupervisedStudentSignaturesView,
    SupervisedStudentsView,
)
from .email_precheck import EmailCheckStartView, EmailCheckStatusView
from .registration_sheet import RegistrationSheetView
from .registration_intake import (
    RegistrationCountriesView,
    RegistrationGroupCodeView,
    RegistrationGroupJoinView,
    RegistrationIntakeView,
    RegistrationManagementView,
    RegistrationStatesView,
    RegistrationUniversitiesView,
)

urlpatterns = [
    path("users/me/profile-options/", StudentProfileOptionsView.as_view(), name="student-profile-options"),
    path("users/me/guardian-invitation/", GuardianInvitationView.as_view(), name="guardian-invitation"),
    path("login/", PasswordLoginView.as_view(), name="password-login"),
    path("set-password/", SetPasswordView.as_view(), name="set-password"),
    path("users/me/", MeRetrieveView.as_view(), name="MeListHTMLView"),
    path("users/me/guardian/", MeGuardianView.as_view(), name="me-guardian"),
    path("users/supervised-students/", SupervisedStudentsView.as_view(), name="supervised-students"),
    path("users/supervised-students/email/", SupervisedStudentEmailView.as_view(), name="supervised-students-email"),
    path("users/supervised-students/options/", SupervisedStudentOptionsView.as_view(), name="supervised-students-options"),
    path("users/supervised-students/signatures/", SupervisedStudentSignaturesView.as_view(), name="supervised-students-signatures"),
    path(
        "users/supervised-students/consent-links/",
        SupervisedStudentConsentLinksView.as_view(),
        name="supervised-students-consent-links",
    ),
    path(
        "users/supervised-students/details-links/",
        SupervisedStudentDetailsLinksView.as_view(),
        name="supervised-students-details-links",
    ),
    path(
        "users/supervised-students/guardian-upload/",
        SupervisedGuardianUploadView.as_view(),
        name="supervised-students-guardian-upload",
    ),
    path("users/supervised-students/<int:pk>/", SupervisedStudentDetailView.as_view(), name="supervised-student-detail"),
    path("users/supervised-groups/mentors/", SupervisedMentorsView.as_view(), name="supervised-mentors"),
    path("users/supervised-groups/interests/", SupervisedInterestCatalogView.as_view(), name="supervised-group-interests"),
    path("users/supervised-groups/", SupervisedGroupsView.as_view(), name="supervised-groups"),
    path("users/supervised-groups/order/", SupervisedGroupOrderView.as_view(), name="supervised-group-order"),
    # My Groups' Waiting Area: Create all groups.
    path("users/supervised-groups/place/", SupervisedGroupsPlaceView.as_view(), name="supervised-groups-place"),
    path("users/supervised-groups/<int:pk>/members/", SupervisedGroupMembersView.as_view(), name="supervised-group-members"),
    path("users/supervised-groups/<int:pk>/", SupervisedGroupDetailView.as_view(), name="supervised-group-detail"),
    path("users/<int:pk>/", UsersRetrieveUpdateView.as_view(), name="user-detail"),
    path("users/", UserListHTMLView.as_view(), name="UserListHTMLView"),
    path("users/me/profile-image/", ProfileImageUploadView.as_view(), name="profile-image-upload"),
    path("registration", RegistrationIntakeView.as_view(), name="registration"),
    path("registration/", RegistrationIntakeView.as_view(), name="registration-slash"),
    path("registration-intake/", RegistrationIntakeView.as_view(), name="registration-intake"),
    path("registration/countries/", RegistrationCountriesView.as_view(), name="registration-countries"),
    path("registration/group-code/", RegistrationGroupCodeView.as_view(), name="registration-group-code"),
    path("registration/group-code/<str:code>/", RegistrationGroupJoinView.as_view(), name="registration-group-join"),
    path("registration/states/", RegistrationStatesView.as_view(), name="registration-states"),
    path("registration/universities/", RegistrationUniversitiesView.as_view(), name="registration-universities"),
    # Upload student details, from an .xlsx: its first sheet as CSV text.
    path("registration/sheet/", RegistrationSheetView.as_view(), name="registration-sheet"),
    # Check a registration's addresses before it's submitted (EMAIL_PRECHECK_ENABLED).
    path("registration/email-check/", EmailCheckStartView.as_view(), name="registration-email-check"),
    path(
        "registration/email-check/<uuid:job_id>/", EmailCheckStatusView.as_view(),
        name="registration-email-check-status",
    ),
    path("registration-management/", RegistrationManagementView.as_view(), name="registration-management"),
    path('updjoinperms', ReceiveJoinPermissionView.as_view(), name = "join_perm"),
    path("consent/<str:token>/", GuardianConsentView.as_view(), name="guardian-consent"),
    path("guardian-details/<str:token>/", GuardianDetailsFormView.as_view(), name="guardian-details-form"),
    path("admin/summary/", AdminOperationalSummaryView.as_view(), name="admin-summary"),
    path("admin/users/bulk-status/", BulkUserStatusView.as_view(), name="admin-bulk-user-status"),
    path(
        "admin/send-guardian-details-reminders/",
        SendGuardianDetailsRemindersView.as_view(),
        name="guardian-details-reminders",
    ),
    path(
        "admin/send-guardian-consent-reminders/",
        SendGuardianConsentRemindersView.as_view(),
        name="guardian-consent-reminders",
    ),
    # The supervisors' daily registration status email.
    path(
        "admin/send-supervisor-registration-status/",
        SendSupervisorRegistrationStatusView.as_view(),
        name="supervisor-registration-status",
    ),
]
