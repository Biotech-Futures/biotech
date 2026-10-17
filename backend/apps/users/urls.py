from django.urls import path
from .profile_options import StudentProfileOptionsView, GuardianInvitationView
from .consent_views import GuardianConsentView, GuardianDetailsFormView
from .guardian_details_views import SendGuardianConsentRemindersView, SendGuardianDetailsRemindersView
from .supervisor_group_views import (
    SupervisedGroupDetailView,
    SupervisedGroupMembersView,
    SupervisedGroupOrderView,
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
from .registration_sheet import RegistrationSheetView
from .registration_intake import (
    RegistrationCountriesView,
    RegistrationGroupCodeView,
    RegistrationGroupJoinView,
    RegistrationIntakeView,
    RegistrationManagementView,
    RegistrationStatesView,
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
    # Upload student details, from an .xlsx: its first sheet as CSV text.
    path("registration/sheet/", RegistrationSheetView.as_view(), name="registration-sheet"),
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
]
