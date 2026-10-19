from .deadline import GroupExtensionDetailView, GroupExtensionListView, SubmissionDeadlineView
from .finalist import FinalistEmailPreviewView, FinalistEmailSettingsView, FinalistNotifyAllView
from .group_results import GroupResultsCertificateView, GroupResultsSummaryView, GroupResultsView
from .nonfinalist import (
    NonFinalistEmailPreviewView,
    NonFinalistEmailSendView,
    NonFinalistEmailView,
    NonSubmissionEmailPreviewView,
    NonSubmissionEmailSendView,
    NonSubmissionEmailView,
)
from .outcome_announcement import (
    AnnouncementCategoriesView,
    OutcomeAnnouncementPostView,
    OutcomeAnnouncementView,
)
from .presentation import (
    PresentationAllocationView,
    PresentationResponsesView,
    PresentationSlidesFileView,
    PresentationSlidesView,
    PresentationSlotDetailView,
    PresentationSlotListView,
    PresentationTimesShownView,
)
from .release import CertificatesReleaseView, MarksReleaseView
from .bounce_check import BounceCheckTriggerView
from .waiting_emails import SendWaitingEmailsView
from .challenge_start import ChallengeStartView
from .registration_open import RegistrationOpenView
from .registration_supervisors import RegistrationSupervisorsView, RegistrationSupervisorView
from .supervisor_pages import SupervisorPagesView
from .supervisor_results import (
    AllResultsCertificatesZipView,
    AllResultsCertificateView,
    AllResultsSheetView,
    AllResultsView,
    SupervisorResultsCertificatesZipView,
    SupervisorResultsCertificateView,
    SupervisorResultsSheetView,
    SupervisorResultsStateView,
    SupervisorResultsView,
)
from .results import (
    ResultsEmailPreviewView,
    ResultsEmailSendView,
    ResultsEmailSettingsView,
    ResultsSampleSheetView,
    ResultsSupervisorSheetView,
)
from .settings import (
    GradingSettingsView,
    TemplateDownloadView,
    TemplatePeopleView,
    TemplateScanView,
    TemplateTestRenderView,
)
from .test_email import TestEmailView

__all__ = [
    "AnnouncementCategoriesView",
    "CertificatesReleaseView",
    "FinalistEmailPreviewView",
    "FinalistEmailSettingsView",
    "FinalistNotifyAllView",
    "GradingSettingsView",
    "BounceCheckTriggerView",
    "SendWaitingEmailsView",
    "ChallengeStartView",
    "RegistrationOpenView",
    "RegistrationSupervisorsView",
    "RegistrationSupervisorView",
    "SupervisorPagesView",
    "AllResultsCertificatesZipView",
    "AllResultsCertificateView",
    "AllResultsSheetView",
    "AllResultsView",
    "SupervisorResultsCertificatesZipView",
    "SupervisorResultsCertificateView",
    "SupervisorResultsSheetView",
    "SupervisorResultsStateView",
    "SupervisorResultsView",
    "GroupExtensionDetailView",
    "GroupExtensionListView",
    "GroupResultsCertificateView",
    "GroupResultsSummaryView",
    "GroupResultsView",
    "MarksReleaseView",
    "NonFinalistEmailPreviewView",
    "NonFinalistEmailSendView",
    "NonFinalistEmailView",
    "NonSubmissionEmailPreviewView",
    "NonSubmissionEmailSendView",
    "NonSubmissionEmailView",
    "OutcomeAnnouncementPostView",
    "OutcomeAnnouncementView",
    "PresentationAllocationView",
    "PresentationResponsesView",
    "PresentationSlidesFileView",
    "PresentationSlidesView",
    "PresentationSlotDetailView",
    "PresentationSlotListView",
    "PresentationTimesShownView",
    "ResultsEmailPreviewView",
    "ResultsEmailSendView",
    "ResultsEmailSettingsView",
    "ResultsSampleSheetView",
    "ResultsSupervisorSheetView",
    "SubmissionDeadlineView",
    "TemplateDownloadView",
    "TemplatePeopleView",
    "TemplateScanView",
    "TemplateTestRenderView",
    "TestEmailView",
]
