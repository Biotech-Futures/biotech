import { relations } from "drizzle-orm/relations";
import { mentorProfile, mentorAvailability, users, adminScope, tracks, userSession, alert, announcements, auditLog, countries, countryStates, events, eventRsvp, groups, groupMembership, matchRun, matchRecommendation, resources, mentorInterest, areasOfInterest, messages, supervisorProfile, studentProfile, userInAdminUser, announcementAudience, roles, mentorCertificate, certificateType, resourceAudience, studentInterest, userRoleAssignment, sessionInAdminUser, accountInAdminUser } from "./schema";

export const mentorAvailabilityRelations = relations(mentorAvailability, ({one}) => ({
	mentorProfile: one(mentorProfile, {
		fields: [mentorAvailability.mentorUserId],
		references: [mentorProfile.userId]
	}),
}));

export const mentorProfileRelations = relations(mentorProfile, ({many}) => ({
	mentorAvailabilities: many(mentorAvailability),
	mentorInterests: many(mentorInterest),
	mentorCertificates: many(mentorCertificate),
}));

export const adminScopeRelations = relations(adminScope, ({one}) => ({
	user: one(users, {
		fields: [adminScope.userId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [adminScope.trackId],
		references: [tracks.id]
	}),
}));

export const usersRelations = relations(users, ({one, many}) => ({
	adminScopes: many(adminScope),
	announcements: many(announcements),
	auditLogs: many(auditLog),
	events: many(events),
	eventRsvps: many(eventRsvp),
	groupMemberships: many(groupMembership),
	matchRuns: many(matchRun),
	matchRecommendations: many(matchRecommendation),
	resources: many(resources),
	messages: many(messages),
	userInAdminUser: one(userInAdminUser, {
		fields: [users.adminUserId],
		references: [userInAdminUser.id]
	}),
	userSessions: many(userSession),
	mentorCertificates: many(mentorCertificate),
	userRoleAssignments: many(userRoleAssignment),
}));

export const tracksRelations = relations(tracks, ({one, many}) => ({
	adminScopes: many(adminScope),
	announcements: many(announcements),
	events: many(events),
	groups: many(groups),
	matchRuns: many(matchRun),
	resources: many(resources),
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
	announcementAudiences: many(announcementAudience),
	resourceAudiences: many(resourceAudience),
}));

export const alertRelations = relations(alert, ({one}) => ({
	userSession: one(userSession, {
		fields: [alert.sessionId],
		references: [userSession.id]
	}),
}));

export const userSessionRelations = relations(userSession, ({one, many}) => ({
	alerts: many(alert),
	user: one(users, {
		fields: [userSession.userId],
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

export const auditLogRelations = relations(auditLog, ({one}) => ({
	user: one(users, {
		fields: [auditLog.actorUserId],
		references: [users.id]
	}),
}));

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

export const eventsRelations = relations(events, ({one, many}) => ({
	user: one(users, {
		fields: [events.hostUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [events.trackId],
		references: [tracks.id]
	}),
	eventRsvps: many(eventRsvp),
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

export const groupsRelations = relations(groups, ({one, many}) => ({
	track: one(tracks, {
		fields: [groups.trackId],
		references: [tracks.id]
	}),
	groupMemberships: many(groupMembership),
	matchRecommendations: many(matchRecommendation),
	messages: many(messages),
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
	matchRun: one(matchRun, {
		fields: [matchRecommendation.matchRunId],
		references: [matchRun.id]
	}),
	group: one(groups, {
		fields: [matchRecommendation.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [matchRecommendation.mentorUserId],
		references: [users.id]
	}),
}));

export const resourcesRelations = relations(resources, ({one, many}) => ({
	user: one(users, {
		fields: [resources.uploaderUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [resources.trackId],
		references: [tracks.id]
	}),
	resourceAudiences: many(resourceAudience),
}));

export const mentorInterestRelations = relations(mentorInterest, ({one}) => ({
	mentorProfile: one(mentorProfile, {
		fields: [mentorInterest.mentorUserId],
		references: [mentorProfile.userId]
	}),
	areasOfInterest: one(areasOfInterest, {
		fields: [mentorInterest.interestId],
		references: [areasOfInterest.id]
	}),
}));

export const areasOfInterestRelations = relations(areasOfInterest, ({many}) => ({
	mentorInterests: many(mentorInterest),
	studentInterests: many(studentInterest),
}));

export const messagesRelations = relations(messages, ({one}) => ({
	group: one(groups, {
		fields: [messages.groupId],
		references: [groups.id]
	}),
	user: one(users, {
		fields: [messages.senderUserId],
		references: [users.id]
	}),
}));

export const studentProfileRelations = relations(studentProfile, ({one, many}) => ({
	supervisorProfile: one(supervisorProfile, {
		fields: [studentProfile.supervisorUserId],
		references: [supervisorProfile.userId]
	}),
	studentInterests: many(studentInterest),
}));

export const supervisorProfileRelations = relations(supervisorProfile, ({many}) => ({
	studentProfiles: many(studentProfile),
}));

export const userInAdminUserRelations = relations(userInAdminUser, ({many}) => ({
	users: many(users),
	sessionInAdminUsers: many(sessionInAdminUser),
	accountInAdminUsers: many(accountInAdminUser),
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
	resourceAudiences: many(resourceAudience),
	userRoleAssignments: many(userRoleAssignment),
}));

export const mentorCertificateRelations = relations(mentorCertificate, ({one}) => ({
	mentorProfile: one(mentorProfile, {
		fields: [mentorCertificate.mentorProfileId],
		references: [mentorProfile.userId]
	}),
	certificateType: one(certificateType, {
		fields: [mentorCertificate.certificateTypeId],
		references: [certificateType.id]
	}),
	user: one(users, {
		fields: [mentorCertificate.verifiedByUserId],
		references: [users.id]
	}),
}));

export const certificateTypeRelations = relations(certificateType, ({many}) => ({
	mentorCertificates: many(mentorCertificate),
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

export const studentInterestRelations = relations(studentInterest, ({one}) => ({
	studentProfile: one(studentProfile, {
		fields: [studentInterest.studentUserId],
		references: [studentProfile.userId]
	}),
	areasOfInterest: one(areasOfInterest, {
		fields: [studentInterest.interestId],
		references: [areasOfInterest.id]
	}),
}));

export const userRoleAssignmentRelations = relations(userRoleAssignment, ({one}) => ({
	user: one(users, {
		fields: [userRoleAssignment.userId],
		references: [users.id]
	}),
	role: one(roles, {
		fields: [userRoleAssignment.roleId],
		references: [roles.id]
	}),
}));

export const sessionInAdminUserRelations = relations(sessionInAdminUser, ({one}) => ({
	userInAdminUser: one(userInAdminUser, {
		fields: [sessionInAdminUser.userId],
		references: [userInAdminUser.id]
	}),
}));

export const accountInAdminUserRelations = relations(accountInAdminUser, ({one}) => ({
	userInAdminUser: one(userInAdminUser, {
		fields: [accountInAdminUser.userId],
		references: [userInAdminUser.id]
	}),
}));