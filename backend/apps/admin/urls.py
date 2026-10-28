from django.urls import include, path
from . import views
from . import analytics_views
from .import_email_check import ImportEmailCheckStatusView, ImportEmailCheckView
from .user_email_check import UserEmailCheckView

app_name = 'admin_api'

urlpatterns = [
    path('analytics/group-activity/', analytics_views.GroupActivityAnalyticsView.as_view(), name='group-activity-analytics'),
    path('analytics/login-activity/', analytics_views.LoginActivityAnalyticsView.as_view(), name='login-activity-analytics'),
    path('analytics/resources/', analytics_views.ResourceAnalyticsView.as_view(), name='resource-analytics'),
    path('analytics/email/', analytics_views.EmailDeliveryAnalyticsView.as_view(), name='email-delivery-analytics'),
    path('analytics/email/recipients/', analytics_views.EmailRecipientSearchView.as_view(), name='email-recipient-search'),
    path('analytics/email/sends/<int:send_id>/recipients/', analytics_views.EmailSendRecipientsView.as_view(), name='email-send-recipients'),
    path('analytics/email/sends/<int:send_id>/recipients/export/', analytics_views.EmailSendRecipientsExportView.as_view(), name='email-send-recipients-export'),
    path('analytics/reports/export/', analytics_views.ReportExportView.as_view(), name='analytics-report-export'),
    # ========================================================================
    # USER ROUTES
    # ========================================================================
    path('user/', views.UserListCreateView.as_view(), name='user-list-create'),
    path('user/countries/', views.UserCountriesListView.as_view(), name='user-countries-list'),
    path('user/states/', views.UserStatesListView.as_view(), name='user-states-list'),
    path('user/bulk/', views.UserBulkCreateView.as_view(), name='user-bulk-create'),
    path('user/bulk-csv/', views.UserBulkCsvView.as_view(), name='user-bulk-csv'),
    path('user/bulk-status/', views.UserBulkStatusUpdateView.as_view(), name='user-bulk-status-update'),
    path('user/bulk-delete/', views.UserBulkDeleteView.as_view(), name='user-bulk-delete'),
    path('user/ungrouped-check/', views.UserUngroupedCheckView.as_view(), name='user-ungrouped-check'),
    # Add user's email boxes, checked as each is left.
    path('user/email-check/', UserEmailCheckView.as_view(), name='user-email-check'),
    # Import Students / Import Mentors: the file's addresses, before Import.
    path('user/import-check/', ImportEmailCheckView.as_view(), name='user-import-check'),
    path('user/import-check/<uuid:job_id>/', ImportEmailCheckStatusView.as_view(), name='user-import-check-status'),
    path('user/<str:user_id>/', views.UserDetailView.as_view(), name='user-detail'),
    path('user/<str:user_id>/status/', views.UserStatusUpdateView.as_view(), name='user-status-update'),
    path('user/<str:user_id>/supervisees/', views.UserSuperviseesView.as_view(), name='user-supervisees'),
    path('user/<str:user_id>/profile-image/', views.UserProfileImageView.as_view(), name='user-profile-image'),
    path('user/<str:user_id>/guardian-consent-request/', views.UserGuardianConsentRequestView.as_view(), name='user-guardian-consent-request'),
    path('user/<str:user_id>/guardian-consents/', views.UserGuardianConsentsView.as_view(), name='user-guardian-consents'),
    path('user/<str:user_id>/guardian-consents/<int:consent_id>/record/', views.UserGuardianConsentRecordView.as_view(), name='user-guardian-consent-record'),
    path('user/<str:user_id>/guardian-consent-withdrawal/', views.UserGuardianConsentWithdrawView.as_view(), name='user-guardian-consent-withdrawal'),
    
    # ========================================================================
    # GROUP ROUTES
    # ========================================================================
    path('group/', views.GroupListView.as_view(), name='group-list'),
    path('group/bulk-delete/', views.GroupBulkDeleteView.as_view(), name='group-bulk-delete'),
    # Must precede the <str:group_id> route, which would otherwise swallow the literal segment.
    path('group/next-name/', views.GroupNextNameView.as_view(), name='group-next-name'),
    path('group/<str:group_id>/', views.GroupDetailView.as_view(), name='group-detail'),
    path('group/<str:group_id>/messages/', views.GroupMessagesListView.as_view(), name='group-messages-list'),
    path('group/<str:group_id>/messages/<str:message_id>/', views.GroupMessageDetailView.as_view(), name='group-message-detail'),
    path('group/<str:group_id>/members/<str:user_id>/', views.GroupMemberRemoveView.as_view(), name='group-member-remove'),
    
    # ========================================================================
    # MATCH ROUTES
    # ========================================================================
    path('match/student/', views.MatchStudentView.as_view(), name='match-student'),
    path('match/individual/', views.MatchIndividualView.as_view(), name='match-individual'),
    path('match/student-suggestions/', views.MatchStudentSuggestionsView.as_view(), name='match-student-suggestions'),
    path('match/confirm/', views.MatchConfirmView.as_view(), name='match-confirm'),
    
    # ========================================================================
    # EVENT ROUTES
    # ========================================================================
    path('event/', views.EventListCreateView.as_view(), name='event-list-create'),
    path('event/<str:event_id>/upload-image/', views.EventImageUploadView.as_view(), name='event-image-upload'),
    path('event/<str:event_id>/', views.EventDetailView.as_view(), name='event-detail'),
    path('event/<str:event_id>/rsvp/', views.EventRsvpListCreateView.as_view(), name='event-rsvp-list-create'),
    path('event/<str:event_id>/targets/', views.EventTargetsView.as_view(), name='event-targets'),
    path('event/meta/groups/', views.EventMetaGroupsView.as_view(), name='event-meta-groups'),
    path('event/meta/roles/', views.EventMetaRolesView.as_view(), name='event-meta-roles'),
    path('event/rsvp/<str:rsvp_id>/', views.EventRsvpDetailView.as_view(), name='event-rsvp-detail'),
    
    # ========================================================================
    # RESOURCE ROUTES
    # ========================================================================
    path('resource/', views.ResourceListCreateView.as_view(), name='resource-list-create'),
    path('resource/<int:resource_id>/', views.ResourceDetailView.as_view(), name='resource-detail'),
    path('resource/<int:resource_id>/access/', views.ResourceAccessView.as_view(), name='resource-access'),
    path('resource/<int:resource_id>/download/', views.ResourceDownloadView.as_view(), name='resource-download'),
    path('resource/<int:resource_id>/upload/', views.ResourceFileReplaceView.as_view(), name='resource-file-replace'),
    path('resource/<int:resource_id>/assign-role/', views.ResourceAssignRoleView.as_view(), name='resource-assign-role'),
    path('resource/<int:resource_id>/remove-role/', views.ResourceRemoveRoleView.as_view(), name='resource-remove-role'),
    path('resource/upload/', views.ResourceUploadView.as_view(), name='resource-upload'),
    path('resource/roles/', views.ResourceRolesListView.as_view(), name='resource-roles-list'),
    path('resource/types/', views.ResourceTypesListView.as_view(), name='resource-types-list'),
    
    # ========================================================================
    # ANNOUNCEMENT ROUTES
    # ========================================================================
    path('announcement/', views.AnnouncementListCreateView.as_view(), name='announcement-list-create'),
    path('announcement/<int:announcement_id>/', views.AnnouncementDetailView.as_view(), name='announcement-detail'),
    path('announcement/<int:announcement_id>/archive/', views.AnnouncementArchiveView.as_view(), name='announcement-archive'),
    path('announcement/<int:announcement_id>/notify/', views.AnnouncementNotifyView.as_view(), name='announcement-notify'),
    path('announcement/groups/', views.AnnouncementGroupsListView.as_view(), name='announcement-groups-list'),
    path('announcement/roles/', views.AnnouncementRolesListView.as_view(), name='announcement-roles-list'),
    path('announcement/merge-tags/', views.AnnouncementMergeTagsView.as_view(), name='announcement-merge-tags'),
    
    # ========================================================================
    # MENTOR ROUTES
    # ========================================================================
    path('mentor/', views.MentorListView.as_view(), name='mentor-list'),
    path('mentor/<int:mentor_id>/active/', views.MentorActiveStatusUpdateView.as_view(), name='mentor-active-status'),
    
    # ========================================================================
    # TASK ROUTES
    # ========================================================================
    path('task/', views.AdminTaskListCreateView.as_view(), name='admin-task-list-create'),
    path('task/<int:task_id>/', views.AdminTaskDetailView.as_view(), name='admin-task-detail'),
    path('task/<int:task_id>/toggle/', views.AdminTaskToggleView.as_view(), name='admin-task-toggle'),

    # ========================================================================
    # ROLE TASK ROUTES
    # ========================================================================
    path('role-task/', views.AdminRoleTaskListCreateView.as_view(), name='admin-role-task-list-create'),
    # Must precede the <int:role_task_id> route so the literal segment wins.
    path('role-task/role-recipients/', views.AdminRoleTaskRoleRecipientsView.as_view(), name='admin-role-task-role-recipients'),
    path('role-task/<int:role_task_id>/', views.AdminRoleTaskDetailView.as_view(), name='admin-role-task-detail'),

    # ========================================================================
    # ADMIN AUTH ROUTES
    # ========================================================================
    path('auth/password-status/', views.AdminPasswordStatusView.as_view(), name='admin-password-status'),
    path('auth/set-password/', views.AdminSetPasswordView.as_view(), name='admin-set-password'),

    # ========================================================================
    # MENTOR MATCH ROUTES
    # ========================================================================
    path('mentor-match/recommend/', views.MentorMatchRecommendView.as_view(), name='mentor-match-recommend'),
    path('mentor-match/mentors/', views.MentorMatchMentorsListView.as_view(), name='mentor-match-mentors-list'),
    path('mentor-match/groups/', views.MentorMatchGroupsListView.as_view(), name='mentor-match-groups-list'),
    path('mentor-match/matched-groups/', views.MentorMatchMatchedGroupsListView.as_view(), name='mentor-match-matched-groups-list'),
    path('mentor-match/confirm/', views.MentorMatchConfirmView.as_view(), name='mentor-match-confirm'),
    path('mentor-match/replace/', views.MentorMatchReplaceView.as_view(), name='mentor-match-replace'),
    path('mentor-match/replace-suggestions/', views.MentorMatchReplaceSuggestionsView.as_view(), name='mentor-match-replace-suggestions'),
    path('mentor-match/unassign/', views.MentorMatchUnassignView.as_view(), name='mentor-match-unassign'),

    # ========================================================================
    # SYSTEM EMAIL ROUTES
    # ========================================================================
    path('email-template/', views.SystemEmailTemplateListView.as_view(), name='email-template-list'),
    # Literal sub-paths precede <str:key> so they are never swallowed as a key.
    path('email-template/<str:key>/preview/', views.SystemEmailTemplatePreviewView.as_view(), name='email-template-preview'),
    path('email-template/<str:key>/test-send/', views.SystemEmailTemplateTestSendView.as_view(), name='email-template-test-send'),
    path('email-template/<str:key>/test-recipients/', views.SystemEmailTemplateTestRecipientsView.as_view(), name='email-template-test-recipients'),
    path('email-template/<str:key>/restore-default/', views.SystemEmailTemplateRestoreView.as_view(), name='email-template-restore'),
    path('email-template/<str:key>/', views.SystemEmailTemplateDetailView.as_view(), name='email-template-detail'),
    path('email-settings/', views.SystemEmailSettingsView.as_view(), name='email-settings'),
    path('email-settings/always-on/', views.SystemEmailAlwaysOnView.as_view(), name='email-settings-always-on'),
    path('scheduled-jobs/', views.ScheduledJobsView.as_view(), name='scheduled-jobs'),
    path('email-log/', views.SystemEmailLogView.as_view(), name='email-log'),
    path('email-log/unseen/', views.SystemEmailUnseenFailuresView.as_view(), name='email-log-unseen'),
    path('email-log/mail-api/', views.SystemEmailMailApiView.as_view(), name='email-log-mail-api'),
    path('email-log/<str:key>/resend/', views.SystemEmailResendView.as_view(), name='email-log-resend'),

    # ========================================================================
    # USER VIEW ROUTES
    # ========================================================================
    path('view/', views.AdminViewListCreateView.as_view(), name='view-list-create'),
    path('view/bulk-delete/', views.AdminViewBulkDeleteView.as_view(), name='view-bulk-delete'),
    path('view/<int:view_id>/', views.AdminViewDetailView.as_view(), name='view-detail'),
    path('view/<int:view_id>/run/', views.AdminViewRunView.as_view(), name='view-run'),
    path('view/<int:view_id>/export-csv/', views.AdminViewExportCsvView.as_view(), name='view-export-csv'),

    # ========================================================================
    # SYSTEM LOG ROUTES (apps.system_logs)
    # ========================================================================
    path('system-logs/', include('apps.system_logs.urls')),

    # ========================================================================
    # EMAIL VERIFICATION ROUTES
    # ========================================================================
    path('email-verification/credits/', views.EmailVerificationCreditsView.as_view(), name='email-verification-credits'),
    path('email-verification/requests/', views.EmailVerificationRequestsView.as_view(), name='email-verification-requests'),

    # ========================================================================
    # KNOWN UNIVERSITY ROUTES
    # ========================================================================
    path('known-university/', views.KnownUniversityListCreateView.as_view(), name='known-university-list-create'),
    path('known-university/<int:university_id>/', views.KnownUniversityDetailView.as_view(), name='known-university-detail'),
    path('known-university/upload/', views.KnownUniversityUploadView.as_view(), name='known-university-upload'),

    # ========================================================================
    # GROUP PLAN ROUTES (builder and progress; literal progress precedes task IDs)
    # ========================================================================
    path('plan-stage/', views.AdminPlanStageListCreateView.as_view(), name='admin-plan-stage-list-create'),
    path('plan-stage/<int:stage_id>/', views.AdminPlanStageDetailView.as_view(), name='admin-plan-stage-detail'),
    path('plan-task/', views.AdminPlanTaskListCreateView.as_view(), name='admin-plan-task-list-create'),
    path('plan-task/progress/', views.AdminPlanProgressView.as_view(), name='admin-plan-progress'),
    path('plan-task/<int:task_id>/', views.AdminPlanTaskDetailView.as_view(), name='admin-plan-task-detail'),
]
