import { relations } from "drizzle-orm/relations";
import { tracks, adminScope, users, userSession, alert, announcements, announcementAudience, roles, adminUser, matchRun, areasOfInterest, mentorInterest, mentorProfile, resources, resourceAudience, events, eventRsvp, groups, groupMembership, mentorAvailability, certificateType, mentorCertificate, messages, studentInterest, studentProfile, account, countryStates, auditLog, countries, session, supervisorProfile, userRoleAssignment } from "./schema";

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

export const tracksRelations = relations(tracks, ({one, many}) => ({
	adminScopes: many(adminScope),
	announcements: many(announcements),
	announcementAudiences: many(announcementAudience),
	resourceAudiences: many(resourceAudience),
	events: many(events),
	groups: many(groups),
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
	resources: many(resources),
}));

export const usersRelations = relations(users, ({one, many}) => ({
	adminScopes: many(adminScope),
	announcements: many(announcements),
	events: many(events),
	eventRsvps: many(eventRsvp),
	groupMemberships: many(groupMembership),
	mentorCertificates: many(mentorCertificate),
	messages: many(messages),
	adminUser: one(adminUser, {
		fields: [users.adminUserId],
		references: [adminUser.id]
	}),
	userSessions: many(userSession),
	auditLogs: many(auditLog),
	resources: many(resources),
	userRoleAssignments: many(userRoleAssignment),
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

export const matchRunRelations = relations(matchRun, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [matchRun.adminUserId],
		references: [adminUser.id]
	}),
}));

export const adminUserRelations = relations(adminUser, ({many}) => ({
	matchRuns: many(matchRun),
	accounts: many(account),
	users: many(users),
	sessions: many(session),
}));

export const mentorInterestRelations = relations(mentorInterest, ({one}) => ({
	areasOfInterest: one(areasOfInterest, {
		fields: [mentorInterest.interestId],
		references: [areasOfInterest.id]
	}),
	mentorProfile: one(mentorProfile, {
		fields: [mentorInterest.mentorUserId],
		references: [mentorProfile.userId]
	}),
}));

export const areasOfInterestRelations = relations(areasOfInterest, ({many}) => ({
	mentorInterests: many(mentorInterest),
	studentInterests: many(studentInterest),
}));

export const mentorProfileRelations = relations(mentorProfile, ({many}) => ({
	mentorInterests: many(mentorInterest),
	mentorAvailabilities: many(mentorAvailability),
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

export const resourcesRelations = relations(resources, ({one, many}) => ({
	resourceAudiences: many(resourceAudience),
	track: one(tracks, {
		fields: [resources.trackId],
		references: [tracks.id]
	}),
	user: one(users, {
		fields: [resources.uploaderUserId],
		references: [users.id]
	}),
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

export const mentorAvailabilityRelations = relations(mentorAvailability, ({one}) => ({
	mentorProfile: one(mentorProfile, {
		fields: [mentorAvailability.mentorUserId],
		references: [mentorProfile.userId]
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
	user: one(users, {
		fields: [mentorCertificate.verifiedByUserId],
		references: [users.id]
	}),
}));

export const certificateTypeRelations = relations(certificateType, ({many}) => ({
	mentorCertificates: many(mentorCertificate),
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

export const studentInterestRelations = relations(studentInterest, ({one}) => ({
	areasOfInterest: one(areasOfInterest, {
		fields: [studentInterest.interestId],
		references: [areasOfInterest.id]
	}),
	studentProfile: one(studentProfile, {
		fields: [studentInterest.studentUserId],
		references: [studentProfile.userId]
	}),
}));

export const studentProfileRelations = relations(studentProfile, ({one, many}) => ({
	studentInterests: many(studentInterest),
	supervisorProfile: one(supervisorProfile, {
		fields: [studentProfile.supervisorUserId],
		references: [supervisorProfile.userId]
	}),
}));

export const accountRelations = relations(account, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [account.userId],
		references: [adminUser.id]
	}),
}));

export const countryStatesRelations = relations(countryStates, ({one, many}) => ({
	tracks: many(tracks),
	country: one(countries, {
		fields: [countryStates.countryId],
		references: [countries.id]
	}),
}));

export const auditLogRelations = relations(auditLog, ({one}) => ({
	user: one(users, {
		fields: [auditLog.actorUserId],
		references: [users.id]
	}),
}));

export const countriesRelations = relations(countries, ({many}) => ({
	countryStates: many(countryStates),
}));

export const sessionRelations = relations(session, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [session.userId],
		references: [adminUser.id]
	}),
}));

export const supervisorProfileRelations = relations(supervisorProfile, ({many}) => ({
	studentProfiles: many(studentProfile),
}));

export const userRoleAssignmentRelations = relations(userRoleAssignment, ({one}) => ({
	role: one(roles, {
		fields: [userRoleAssignment.roleId],
		references: [roles.id]
	}),
	user: one(users, {
		fields: [userRoleAssignment.userId],
		references: [users.id]
	}),
}));