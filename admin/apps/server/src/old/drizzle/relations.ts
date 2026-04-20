import { relations } from "drizzle-orm/relations";
import { adminUser, users, announcements, announcementAudience, roles, tracks, mentorProfile, mentorAvailability, session, account, userSession, alert, auditLog, countries, countryStates, events, eventRsvp, groups, groupMembership, areasOfInterest, mentorInterest, resources, matchRun, certificateType, mentorCertificate, messages, resourceAudience, studentInterest, studentProfile, supervisorProfile, userRoleAssignment } from "./schema.js";

export const usersRelations = relations(users, ({one, many}) => ({
	adminUser: one(adminUser, {
		fields: [users.adminUserId],
		references: [adminUser.id]
	}),
	announcements: many(announcements),
	auditLogs: many(auditLog),
	events: many(events),
	eventRsvps: many(eventRsvp),
	groupMemberships: many(groupMembership),
	resources: many(resources),
	mentorCertificates: many(mentorCertificate),
	messages: many(messages),
	userSessions: many(userSession),
	userRoleAssignments: many(userRoleAssignment),
}));

export const adminUserRelations = relations(adminUser, ({many}) => ({
	users: many(users),
	sessions: many(session),
	accounts: many(account),
	matchRuns: many(matchRun),
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

export const announcementsRelations = relations(announcements, ({one, many}) => ({
	announcementAudiences: many(announcementAudience),
	user: one(users, {
		fields: [announcements.authorUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [announcements.trackId],
		references: [tracks.id]
	}),
}));

export const rolesRelations = relations(roles, ({many}) => ({
	announcementAudiences: many(announcementAudience),
	resourceAudiences: many(resourceAudience),
	userRoleAssignments: many(userRoleAssignment),
}));

export const tracksRelations = relations(tracks, ({one, many}) => ({
	announcementAudiences: many(announcementAudience),
	announcements: many(announcements),
	events: many(events),
	resources: many(resources),
	groups: many(groups),
	resourceAudiences: many(resourceAudience),
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
}));

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

export const sessionRelations = relations(session, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [session.userId],
		references: [adminUser.id]
	}),
}));

export const accountRelations = relations(account, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [account.userId],
		references: [adminUser.id]
	}),
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

export const groupsRelations = relations(groups, ({one, many}) => ({
	groupMemberships: many(groupMembership),
	track: one(tracks, {
		fields: [groups.trackId],
		references: [tracks.id]
	}),
	messages: many(messages),
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

export const resourcesRelations = relations(resources, ({one, many}) => ({
	track: one(tracks, {
		fields: [resources.trackId],
		references: [tracks.id]
	}),
	user: one(users, {
		fields: [resources.uploaderUserId],
		references: [users.id]
	}),
	resourceAudiences: many(resourceAudience),
}));

export const matchRunRelations = relations(matchRun, ({one}) => ({
	adminUser: one(adminUser, {
		fields: [matchRun.adminUserId],
		references: [adminUser.id]
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
