from django.urls import path
from . import views

app_name = 'admin_api'

urlpatterns = [
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
    path('user/<str:user_id>/', views.UserDetailView.as_view(), name='user-detail'),
    path('user/<str:user_id>/status/', views.UserStatusUpdateView.as_view(), name='user-status-update'),
    
    # ========================================================================
    # GROUP ROUTES
    # ========================================================================
    path('group/', views.GroupListView.as_view(), name='group-list'),
    path('group/bulk-delete/', views.GroupBulkDeleteView.as_view(), name='group-bulk-delete'),
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
    
    # ========================================================================
    # MENTOR ROUTES
    # ========================================================================
    path('mentor/', views.MentorListView.as_view(), name='mentor-list'),
    path('mentor/<int:mentor_id>/active/', views.MentorActiveStatusUpdateView.as_view(), name='mentor-active-status'),
    
    # ========================================================================
    # TASK ROUTES
    # ========================================================================
    path('task/', views.AdminTaskListCreateView.as_view(), name='admin-task-list-create'),
    # Must precede the <int:task_id> route so the literal segment wins.
    path('task/role-recipients/', views.AdminTaskRoleRecipientsView.as_view(), name='admin-task-role-recipients'),
    path('task/<int:task_id>/', views.AdminTaskDetailView.as_view(), name='admin-task-detail'),
    path('task/<int:task_id>/toggle/', views.AdminTaskToggleView.as_view(), name='admin-task-toggle'),

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
]
