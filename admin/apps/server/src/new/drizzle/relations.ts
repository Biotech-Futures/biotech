import { relations } from "drizzle-orm/relations";
import { countries, countryStates, tracks, djangoContentType, authPermission, authGroupPermissions, authGroup, users, supervisorProfile, studentProfile, usersGroups, usersUserPermissions, adminProfile, adminScope, mentorAvailability, areasOfInterest, userInterest, mentorProfile, studentSupervisor, djangoAdminLog, announcements, announcementAudience, roles, auditLog, certificateType, mentorCertificate, messages, messageResources, resources, messageStatus, groups, events, eventTargetGroup, eventTargetRole, eventTargetTrack, eventRsvp, groupMembership, matchingInterest, matchingMentorInterests, matchingMentor, matchingStudentInterests, matchingStudent, matchingStudentgroup, matchingStudentgroupInterests, matchingStudentgroupMembers, matchingMentoravailability, matchRun, matchRecommendation, roleAssignmentHistory, resourceAudience, loginTokens, milestone, tasks, taskAssignees, userSession, alert, workshops, workshopAttendance, userInAdmin, accountInAdmin, resourceTypes, sessionInAdmin, matchRunInAdmin } from "./schema";

export const countryStatesRelations = relations(countryStates, ({one, many}) => ({
	country: one(countries, {
		fields: [countryStates.countryId],
		references: [countries.id]
	}),
	tracks: many(tracks),
}));

export const countriesRelations = relations(countries, ({many}) => ({
	countryStates: many(countryStates),
}));

export const tracksRelations = relations(tracks, ({one, many}) => ({
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
	users: many(users),
	adminScopes: many(adminScope),
	announcements: many(announcements),
	announcementAudiences: many(announcementAudience),
	events: many(events),
	eventTargetTracks: many(eventTargetTrack),
	groups: many(groups),
	matchRuns: many(matchRun),
	resourceAudiences: many(resourceAudience),
	resources: many(resources),
}));

export const authPermissionRelations = relations(authPermission, ({one, many}) => ({
	djangoContentType: one(djangoContentType, {
		fields: [authPermission.contentTypeId],
		references: [djangoContentType.id]
	}),
	authGroupPermissions: many(authGroupPermissions),
	usersUserPermissions: many(usersUserPermissions),
}));

export const djangoContentTypeRelations = relations(djangoContentType, ({many}) => ({
	authPermissions: many(authPermission),
	djangoAdminLogs: many(djangoAdminLog),
}));

export const authGroupPermissionsRelations = relations(authGroupPermissions, ({one}) => ({
	authPermission: one(authPermission, {
		fields: [authGroupPermissions.permissionId],
		references: [authPermission.id]
	}),
	authGroup: one(authGroup, {
		fields: [authGroupPermissions.groupId],
		references: [authGroup.id]
	}),
}));

export const authGroupRelations = relations(authGroup, ({many}) => ({
	authGroupPermissions: many(authGroupPermissions),
	usersGroups: many(usersGroups),
}));

export const supervisorProfileRelations = relations(supervisorProfile, ({one, many}) => ({
	user: one(users, {
		fields: [supervisorProfile.userId],
		references: [users.id]
	}),
	studentProfiles: many(studentProfile),
	studentSupervisors: many(studentSupervisor),
}));

export const usersRelations = relations(users, ({one, many}) => ({
	supervisorProfiles: many(supervisorProfile),
	studentProfiles: many(studentProfile),
	track: one(tracks, {
		fields: [users.trackId],
		references: [tracks.id]
	}),
	usersGroups: many(usersGroups),
	usersUserPermissions: many(usersUserPermissions),
	adminProfiles: many(adminProfile),
	adminScopes: many(adminScope),
	mentorAvailabilities: many(mentorAvailability),
	userInterests: many(userInterest),
	mentorProfiles: many(mentorProfile),
	djangoAdminLogs: many(djangoAdminLog),
	announcements: many(announcements),
	auditLogs: many(auditLog),
	messageStatuses: many(messageStatus),
	messages: many(messages),
	events: many(events),
	eventRsvps: many(eventRsvp),
	groupMemberships: many(groupMembership),
	matchRuns: many(matchRun),
	matchRecommendations: many(matchRecommendation),
	roleAssignmentHistories: many(roleAssignmentHistory),
	loginTokens: many(loginTokens),
	taskAssignees: many(taskAssignees),
	userSessions: many(userSession),
	workshops: many(workshops),
	workshopAttendances: many(workshopAttendance),
	resources: many(resources),
	userInAdmins: many(userInAdmin),
}));

export const studentProfileRelations = relations(studentProfile, ({one, many}) => ({
	supervisorProfile: one(supervisorProfile, {
		fields: [studentProfile.supervisorId],
		references: [supervisorProfile.userId]
	}),
	user: one(users, {
		fields: [studentProfile.userId],
		references: [users.id]
	}),
	studentSupervisors: many(studentSupervisor),
}));

export const usersGroupsRelations = relations(usersGroups, ({one}) => ({
	authGroup: one(authGroup, {
		fields: [usersGroups.groupId],
		references: [authGroup.id]
	}),
	user: one(users, {
		fields: [usersGroups.userId],
		references: [users.id]
	}),
}));

export const usersUserPermissionsRelations = relations(usersUserPermissions, ({one}) => ({
	authPermission: one(authPermission, {
		fields: [usersUserPermissions.permissionId],
		references: [authPermission.id]
	}),
	user: one(users, {
		fields: [usersUserPermissions.userId],
		references: [users.id]
	}),
}));

export const adminProfileRelations = relations(adminProfile, ({one}) => ({
	user: one(users, {
		fields: [adminProfile.adminId],
		references: [users.id]
	}),
}));

export const adminScopeRelations = relations(adminScope, ({one}) => ({
	track: one(tracks, {
		fields: [adminScope.trackId],
		references: [tracks.id]
	}),
	user: one(users, {
		fields: [adminScope.userId],
		references: [users.id]
	}),
}));

export const mentorAvailabilityRelations = relations(mentorAvailability, ({one}) => ({
	user: one(users, {
		fields: [mentorAvailability.mentorUserId],
		references: [users.id]
	}),
}));

export const userInterestRelations = relations(userInterest, ({one}) => ({
	areasOfInterest: one(areasOfInterest, {
		fields: [userInterest.interestId],
		references: [areasOfInterest.id]
	}),
	user: one(users, {
		fields: [userInterest.userId],
		references: [users.id]
	}),
}));

export const areasOfInterestRelations = relations(areasOfInterest, ({many}) => ({
	userInterests: many(userInterest),
}));

export const mentorProfileRelations = relations(mentorProfile, ({one, many}) => ({
	user: one(users, {
		fields: [mentorProfile.userId],
		references: [users.id]
	}),
	mentorCertificates: many(mentorCertificate),
}));

export const studentSupervisorRelations = relations(studentSupervisor, ({one}) => ({
	studentProfile: one(studentProfile, {
		fields: [studentSupervisor.studentUserId],
		references: [studentProfile.userId]
	}),
	supervisorProfile: one(supervisorProfile, {
		fields: [studentSupervisor.supervisorUserId],
		references: [supervisorProfile.userId]
	}),
}));

export const djangoAdminLogRelations = relations(djangoAdminLog, ({one}) => ({
	djangoContentType: one(djangoContentType, {
		fields: [djangoAdminLog.contentTypeId],
		references: [djangoContentType.id]
	}),
	user: one(users, {
		fields: [djangoAdminLog.userId],
		references: [users.id]
	}),
}));

export const announcementsRelations = relations(announcements, ({one, many}) => ({
	user: one(users, {
		fields: [announcements.authorUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [announcements.trackId],
		references: [tracks.id]
	}),
	announcementAudiences: many(announcementAudience),
}));

export const announcementAudienceRelations = relations(announcementAudience, ({one}) => ({
	announcement: one(announcements, {
		fields: [announcementAudience.announcementId],
		references: [announcements.id]
	}),
	role: one(roles, {
		fields: [announcementAudience.roleId],
		references: [roles.id]
	}),
	track: one(tracks, {
		fields: [announcementAudience.trackId],
		references: [tracks.id]
	}),
}));

export const rolesRelations = relations(roles, ({many}) => ({
	announcementAudiences: many(announcementAudience),
	eventTargetRoles: many(eventTargetRole),
	roleAssignmentHistories: many(roleAssignmentHistory),
	resourceAudiences: many(resourceAudience),
}));

export const auditLogRelations = relations(auditLog, ({one}) => ({
	user: one(users, {
		fields: [auditLog.actorUserId],
		references: [users.id]
	}),
}));

export const mentorCertificateRelations = relations(mentorCertificate, ({one}) => ({
	certificateType: one(certificateType, {
		fields: [mentorCertificate.certificateTypeId],
		references: [certificateType.id]
	}),
	mentorProfile: one(mentorProfile, {
		fields: [mentorCertificate.mentorProfileId],
		references: [mentorProfile.userId]
	}),
}));

export const certificateTypeRelations = relations(certificateType, ({many}) => ({
	mentorCertificates: many(mentorCertificate),
}));

export const messageResourcesRelations = relations(messageResources, ({one}) => ({
	message: one(messages, {
		fields: [messageResources.messageId],
		references: [messages.id]
	}),
	resource: one(resources, {
		fields: [messageResources.resourceId],
		references: [resources.id]
	}),
}));

export const messagesRelations = relations(messages, ({one, many}) => ({
	messageResources: many(messageResources),
	messageStatuses: many(messageStatus),
	group: one(groups, {
		fields: [messages.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [messages.senderUserId],
		references: [users.id]
	}),
}));

export const resourcesRelations = relations(resources, ({one, many}) => ({
	messageResources: many(messageResources),
	resourceAudiences: many(resourceAudience),
	group: one(groups, {
		fields: [resources.groupId],
		references: [groups.id]
	}),
	track: one(tracks, {
		fields: [resources.trackId],
		references: [tracks.id]
	}),
	resourceType: one(resourceTypes, {
		fields: [resources.typeId],
		references: [resourceTypes.id]
	}),
	user: one(users, {
		fields: [resources.uploadedById],
		references: [users.id]
	}),
}));

export const messageStatusRelations = relations(messageStatus, ({one}) => ({
	message: one(messages, {
		fields: [messageStatus.messageId],
		references: [messages.id]
	}),
	user: one(users, {
		fields: [messageStatus.userId],
		references: [users.id]
	}),
}));

export const groupsRelations = relations(groups, ({one, many}) => ({
	messages: many(messages),
	eventTargetGroups: many(eventTargetGroup),
	groupMemberships: many(groupMembership),
	track: one(tracks, {
		fields: [groups.trackId],
		references: [tracks.id]
	}),
	matchRecommendations: many(matchRecommendation),
	milestones: many(milestone),
	workshops: many(workshops),
	resources: many(resources),
}));

export const eventsRelations = relations(events, ({one, many}) => ({
	user: one(users, {
		fields: [events.hostUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [events.trackId],
		references: [tracks.id]
	}),
	eventTargetGroups: many(eventTargetGroup),
	eventTargetRoles: many(eventTargetRole),
	eventTargetTracks: many(eventTargetTrack),
	eventRsvps: many(eventRsvp),
}));

export const eventTargetGroupRelations = relations(eventTargetGroup, ({one}) => ({
	event: one(events, {
		fields: [eventTargetGroup.eventId],
		references: [events.id]
	}),
	group: one(groups, {
		fields: [eventTargetGroup.groupId],
		references: [groups.id]
	}),
}));

export const eventTargetRoleRelations = relations(eventTargetRole, ({one}) => ({
	event: one(events, {
		fields: [eventTargetRole.eventId],
		references: [events.id]
	}),
	role: one(roles, {
		fields: [eventTargetRole.roleId],
		references: [roles.id]
	}),
}));

export const eventTargetTrackRelations = relations(eventTargetTrack, ({one}) => ({
	event: one(events, {
		fields: [eventTargetTrack.eventId],
		references: [events.id]
	}),
	track: one(tracks, {
		fields: [eventTargetTrack.trackId],
		references: [tracks.id]
	}),
}));

export const eventRsvpRelations = relations(eventRsvp, ({one}) => ({
	event: one(events, {
		fields: [eventRsvp.eventId],
		references: [events.id]
	}),
	user: one(users, {
		fields: [eventRsvp.userId],
		references: [users.id]
	}),
}));

export const groupMembershipRelations = relations(groupMembership, ({one}) => ({
	group: one(groups, {
		fields: [groupMembership.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [groupMembership.userId],
		references: [users.id]
	}),
}));

export const matchingMentorInterestsRelations = relations(matchingMentorInterests, ({one}) => ({
	matchingInterest: one(matchingInterest, {
		fields: [matchingMentorInterests.interestId],
		references: [matchingInterest.id]
	}),
	matchingMentor: one(matchingMentor, {
		fields: [matchingMentorInterests.mentorId],
		references: [matchingMentor.id]
	}),
}));

export const matchingInterestRelations = relations(matchingInterest, ({many}) => ({
	matchingMentorInterests: many(matchingMentorInterests),
	matchingStudentInterests: many(matchingStudentInterests),
	matchingStudentgroupInterests: many(matchingStudentgroupInterests),
}));

export const matchingMentorRelations = relations(matchingMentor, ({many}) => ({
	matchingMentorInterests: many(matchingMentorInterests),
	matchingStudentgroups: many(matchingStudentgroup),
	matchingMentoravailabilities: many(matchingMentoravailability),
}));

export const matchingStudentInterestsRelations = relations(matchingStudentInterests, ({one}) => ({
	matchingInterest: one(matchingInterest, {
		fields: [matchingStudentInterests.interestId],
		references: [matchingInterest.id]
	}),
	matchingStudent: one(matchingStudent, {
		fields: [matchingStudentInterests.studentId],
		references: [matchingStudent.id]
	}),
}));

export const matchingStudentRelations = relations(matchingStudent, ({many}) => ({
	matchingStudentInterests: many(matchingStudentInterests),
	matchingStudentgroupMembers: many(matchingStudentgroupMembers),
}));

export const matchingStudentgroupRelations = relations(matchingStudentgroup, ({one, many}) => ({
	matchingMentor: one(matchingMentor, {
		fields: [matchingStudentgroup.mentorId],
		references: [matchingMentor.id]
	}),
	matchingStudentgroupInterests: many(matchingStudentgroupInterests),
	matchingStudentgroupMembers: many(matchingStudentgroupMembers),
}));

export const matchingStudentgroupInterestsRelations = relations(matchingStudentgroupInterests, ({one}) => ({
	matchingInterest: one(matchingInterest, {
		fields: [matchingStudentgroupInterests.interestId],
		references: [matchingInterest.id]
	}),
	matchingStudentgroup: one(matchingStudentgroup, {
		fields: [matchingStudentgroupInterests.studentgroupId],
		references: [matchingStudentgroup.id]
	}),
}));

export const matchingStudentgroupMembersRelations = relations(matchingStudentgroupMembers, ({one}) => ({
	matchingStudent: one(matchingStudent, {
		fields: [matchingStudentgroupMembers.studentId],
		references: [matchingStudent.id]
	}),
	matchingStudentgroup: one(matchingStudentgroup, {
		fields: [matchingStudentgroupMembers.studentgroupId],
		references: [matchingStudentgroup.id]
	}),
}));

export const matchingMentoravailabilityRelations = relations(matchingMentoravailability, ({one}) => ({
	matchingMentor: one(matchingMentor, {
		fields: [matchingMentoravailability.mentorId],
		references: [matchingMentor.id]
	}),
}));

export const matchRunRelations = relations(matchRun, ({one, many}) => ({
	user: one(users, {
		fields: [matchRun.initiatedByUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [matchRun.trackId],
		references: [tracks.id]
	}),
	matchRecommendations: many(matchRecommendation),
}));

export const matchRecommendationRelations = relations(matchRecommendation, ({one}) => ({
	group: one(groups, {
		fields: [matchRecommendation.groupId],
		references: [groups.id]
	}),
	matchRun: one(matchRun, {
		fields: [matchRecommendation.matchRunId],
		references: [matchRun.id]
	}),
	user: one(users, {
		fields: [matchRecommendation.mentorUserId],
		references: [users.id]
	}),
}));

export const roleAssignmentHistoryRelations = relations(roleAssignmentHistory, ({one}) => ({
	role: one(roles, {
		fields: [roleAssignmentHistory.roleId],
		references: [roles.id]
	}),
	user: one(users, {
		fields: [roleAssignmentHistory.userId],
		references: [users.id]
	}),
}));

export const resourceAudienceRelations = relations(resourceAudience, ({one}) => ({
	resource: one(resources, {
		fields: [resourceAudience.resourceId],
		references: [resources.id]
	}),
	role: one(roles, {
		fields: [resourceAudience.roleId],
		references: [roles.id]
	}),
	track: one(tracks, {
		fields: [resourceAudience.trackId],
		references: [tracks.id]
	}),
}));

export const loginTokensRelations = relations(loginTokens, ({one}) => ({
	user: one(users, {
		fields: [loginTokens.userId],
		references: [users.id]
	}),
}));

export const milestoneRelations = relations(milestone, ({one, many}) => ({
	group: one(groups, {
		fields: [milestone.groupId],
		references: [groups.id]
	}),
	tasks: many(tasks),
}));

export const tasksRelations = relations(tasks, ({one, many}) => ({
	milestone: one(milestone, {
		fields: [tasks.milestoneId],
		references: [milestone.id]
	}),
	taskAssignees: many(taskAssignees),
}));

export const taskAssigneesRelations = relations(taskAssignees, ({one}) => ({
	task: one(tasks, {
		fields: [taskAssignees.taskId],
		references: [tasks.id]
	}),
	user: one(users, {
		fields: [taskAssignees.userId],
		references: [users.id]
	}),
}));

export const userSessionRelations = relations(userSession, ({one, many}) => ({
	user: one(users, {
		fields: [userSession.userId],
		references: [users.id]
	}),
	alerts: many(alert),
}));

export const alertRelations = relations(alert, ({one}) => ({
	userSession: one(userSession, {
		fields: [alert.sessionId],
		references: [userSession.id]
	}),
}));

export const workshopsRelations = relations(workshops, ({one, many}) => ({
	group: one(groups, {
		fields: [workshops.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [workshops.hostUserId],
		references: [users.id]
	}),
	workshopAttendances: many(workshopAttendance),
}));

export const workshopAttendanceRelations = relations(workshopAttendance, ({one}) => ({
	user: one(users, {
		fields: [workshopAttendance.userId],
		references: [users.id]
	}),
	workshop: one(workshops, {
		fields: [workshopAttendance.workshopId],
		references: [workshops.workshopId]
	}),
}));

export const accountInAdminRelations = relations(accountInAdmin, ({one}) => ({
	userInAdmin: one(userInAdmin, {
		fields: [accountInAdmin.userId],
		references: [userInAdmin.id]
	}),
}));

export const userInAdminRelations = relations(userInAdmin, ({one, many}) => ({
	accountInAdmins: many(accountInAdmin),
	user: one(users, {
		fields: [userInAdmin.userId],
		references: [users.id]
	}),
	sessionInAdmins: many(sessionInAdmin),
	matchRunInAdmins: many(matchRunInAdmin),
}));

export const resourceTypesRelations = relations(resourceTypes, ({many}) => ({
	resources: many(resources),
}));

export const sessionInAdminRelations = relations(sessionInAdmin, ({one}) => ({
	userInAdmin: one(userInAdmin, {
		fields: [sessionInAdmin.userId],
		references: [userInAdmin.id]
	}),
}));

export const matchRunInAdminRelations = relations(matchRunInAdmin, ({one}) => ({
	userInAdmin: one(userInAdmin, {
		fields: [matchRunInAdmin.adminUserId],
		references: [userInAdmin.id]
	}),
}));