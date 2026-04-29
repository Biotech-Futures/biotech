import { relations } from "drizzle-orm/relations";
import { users, events, userInAdmin, accountInAdmin, countryStates, tracks, countries, authGroup, usersGroups, authPermission, usersUserPermissions, workshopAttendance, workshops, groups, resources, resourceTypes, resourceAudience, roles, sessionInAdmin, matchRunInAdmin, adminProfile, sessions, alerts, djangoContentType, authGroupPermissions, eventTargetGroup, eventInvite, djangoAdminLog, eventTargetRole, eventTargetTrack, messages, messageResources, background, mentorProfile, messageAttachments, groupMembers, loginTokens, certificateType, mentorCertificate, messageStatus, milestone, areasOfInterest, studentInterest, roleAssignmentHistory, studentProfile, supervisorProfile, relationshipType, studentSupervisor, tasks, taskAssignees } from "./schema";

export const eventsRelations = relations(events, ({one, many}) => ({
	user: one(users, {
		fields: [events.hostUserId],
		references: [users.id]
	}),
	eventTargetGroups: many(eventTargetGroup),
	eventInvites: many(eventInvite),
	eventTargetRoles: many(eventTargetRole),
	eventTargetTracks: many(eventTargetTrack),
}));

export const usersRelations = relations(users, ({one, many}) => ({
	events: many(events),
	countryState: one(countryStates, {
		fields: [users.stateId],
		references: [countryStates.id]
	}),
	track: one(tracks, {
		fields: [users.trackId],
		references: [tracks.id]
	}),
	usersGroups: many(usersGroups),
	usersUserPermissions: many(usersUserPermissions),
	workshopAttendances: many(workshopAttendance),
	workshops: many(workshops),
	resources: many(resources),
	userInAdmins: many(userInAdmin),
	adminProfiles: many(adminProfile),
	eventInvites: many(eventInvite),
	djangoAdminLogs: many(djangoAdminLog),
	mentorProfiles: many(mentorProfile),
	groupMembers: many(groupMembers),
	loginTokens: many(loginTokens),
	messageStatuses: many(messageStatus),
	studentInterests: many(studentInterest),
	messages: many(messages),
	sessions: many(sessions),
	roleAssignmentHistories: many(roleAssignmentHistory),
	studentProfiles: many(studentProfile),
	supervisorProfiles: many(supervisorProfile),
	taskAssignees: many(taskAssignees),
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

export const countryStatesRelations = relations(countryStates, ({one, many}) => ({
	users: many(users),
	country: one(countries, {
		fields: [countryStates.countryId],
		references: [countries.id]
	}),
	tracks: many(tracks),
}));

export const tracksRelations = relations(tracks, ({one, many}) => ({
	users: many(users),
	resources: many(resources),
	resourceAudiences: many(resourceAudience),
	groups: many(groups),
	eventTargetTracks: many(eventTargetTrack),
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
}));

export const countriesRelations = relations(countries, ({many}) => ({
	countryStates: many(countryStates),
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

export const authGroupRelations = relations(authGroup, ({many}) => ({
	usersGroups: many(usersGroups),
	authGroupPermissions: many(authGroupPermissions),
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

export const authPermissionRelations = relations(authPermission, ({one, many}) => ({
	usersUserPermissions: many(usersUserPermissions),
	djangoContentType: one(djangoContentType, {
		fields: [authPermission.contentTypeId],
		references: [djangoContentType.id]
	}),
	authGroupPermissions: many(authGroupPermissions),
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

export const workshopsRelations = relations(workshops, ({one, many}) => ({
	workshopAttendances: many(workshopAttendance),
	group: one(groups, {
		fields: [workshops.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [workshops.hostUserId],
		references: [users.id]
	}),
}));

export const groupsRelations = relations(groups, ({one, many}) => ({
	workshops: many(workshops),
	resources: many(resources),
	eventTargetGroups: many(eventTargetGroup),
	track: one(tracks, {
		fields: [groups.trackId],
		references: [tracks.id]
	}),
	groupMembers: many(groupMembers),
	milestones: many(milestone),
	messages: many(messages),
}));

export const resourcesRelations = relations(resources, ({one, many}) => ({
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
	resourceAudiences: many(resourceAudience),
	messageResources: many(messageResources),
}));

export const resourceTypesRelations = relations(resourceTypes, ({many}) => ({
	resources: many(resources),
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

export const rolesRelations = relations(roles, ({many}) => ({
	resourceAudiences: many(resourceAudience),
	eventTargetRoles: many(eventTargetRole),
	roleAssignmentHistories: many(roleAssignmentHistory),
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

export const adminProfileRelations = relations(adminProfile, ({one}) => ({
	user: one(users, {
		fields: [adminProfile.adminId],
		references: [users.id]
	}),
}));

export const alertsRelations = relations(alerts, ({one}) => ({
	session: one(sessions, {
		fields: [alerts.sessionId],
		references: [sessions.id]
	}),
}));

export const sessionsRelations = relations(sessions, ({one, many}) => ({
	alerts: many(alerts),
	user: one(users, {
		fields: [sessions.userId],
		references: [users.id]
	}),
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

export const eventInviteRelations = relations(eventInvite, ({one}) => ({
	event: one(events, {
		fields: [eventInvite.eventId],
		references: [events.id]
	}),
	user: one(users, {
		fields: [eventInvite.userId],
		references: [users.id]
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
	messageAttachments: many(messageAttachments),
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

export const mentorProfileRelations = relations(mentorProfile, ({one, many}) => ({
	background: one(background, {
		fields: [mentorProfile.backgroundId],
		references: [background.id]
	}),
	user: one(users, {
		fields: [mentorProfile.userId],
		references: [users.id]
	}),
	mentorCertificates: many(mentorCertificate),
}));

export const backgroundRelations = relations(background, ({many}) => ({
	mentorProfiles: many(mentorProfile),
}));

export const messageAttachmentsRelations = relations(messageAttachments, ({one}) => ({
	message: one(messages, {
		fields: [messageAttachments.messageId],
		references: [messages.id]
	}),
}));

export const groupMembersRelations = relations(groupMembers, ({one}) => ({
	group: one(groups, {
		fields: [groupMembers.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [groupMembers.userId],
		references: [users.id]
	}),
}));

export const loginTokensRelations = relations(loginTokens, ({one}) => ({
	user: one(users, {
		fields: [loginTokens.userId],
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

export const milestoneRelations = relations(milestone, ({one, many}) => ({
	group: one(groups, {
		fields: [milestone.groupId],
		references: [groups.id]
	}),
	tasks: many(tasks),
}));

export const studentInterestRelations = relations(studentInterest, ({one}) => ({
	areasOfInterest: one(areasOfInterest, {
		fields: [studentInterest.interestId],
		references: [areasOfInterest.id]
	}),
	user: one(users, {
		fields: [studentInterest.userId],
		references: [users.id]
	}),
}));

export const areasOfInterestRelations = relations(areasOfInterest, ({many}) => ({
	studentInterests: many(studentInterest),
	studentProfiles: many(studentProfile),
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

export const studentProfileRelations = relations(studentProfile, ({one, many}) => ({
	areasOfInterest: one(areasOfInterest, {
		fields: [studentProfile.interestId],
		references: [areasOfInterest.id]
	}),
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

export const supervisorProfileRelations = relations(supervisorProfile, ({one, many}) => ({
	studentProfiles: many(studentProfile),
	user: one(users, {
		fields: [supervisorProfile.userId],
		references: [users.id]
	}),
	studentSupervisors: many(studentSupervisor),
}));

export const studentSupervisorRelations = relations(studentSupervisor, ({one}) => ({
	relationshipType: one(relationshipType, {
		fields: [studentSupervisor.relationshipTypeId],
		references: [relationshipType.relationshipTypeId]
	}),
	studentProfile: one(studentProfile, {
		fields: [studentSupervisor.studentUserId],
		references: [studentProfile.userId]
	}),
	supervisorProfile: one(supervisorProfile, {
		fields: [studentSupervisor.supervisorUserId],
		references: [supervisorProfile.userId]
	}),
}));

export const relationshipTypeRelations = relations(relationshipType, ({many}) => ({
	studentSupervisors: many(studentSupervisor),
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