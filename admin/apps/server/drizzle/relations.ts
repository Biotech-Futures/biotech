import { relations } from "drizzle-orm/relations";
import { studentProfile, studentInterest, areasOfInterest, tracks, users, supervisorProfile, mentorProfile, adminScope, countryStates, countries, mentorInterest, mentorAvailability, groups, groupMembership, resources, resourceAudience, roles, events, eventRsvp, announcements, announcementAudience, userSession, alert, userRoleAssignment, messages, mentorCertificate, certificateType, auditLog, matchRun, matchRecommendation } from "./schema";

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

export const studentProfileRelations = relations(studentProfile, ({one, many}) => ({
	studentInterests: many(studentInterest),
	users: many(users),
	supervisorProfile: one(supervisorProfile, {
		fields: [studentProfile.supervisorUserId],
		references: [supervisorProfile.userId]
	}),
}));

export const areasOfInterestRelations = relations(areasOfInterest, ({many}) => ({
	studentInterests: many(studentInterest),
	mentorInterests: many(mentorInterest),
}));

export const usersRelations = relations(users, ({one, many}) => ({
	track: one(tracks, {
		fields: [users.trackId],
		references: [tracks.id]
	}),
	supervisorProfile: one(supervisorProfile, {
		fields: [users.id],
		references: [supervisorProfile.userId]
	}),
	mentorProfile: one(mentorProfile, {
		fields: [users.id],
		references: [mentorProfile.userId]
	}),
	studentProfile: one(studentProfile, {
		fields: [users.id],
		references: [studentProfile.userId]
	}),
	adminScopes: many(adminScope),
	groupMemberships: many(groupMembership),
	resources: many(resources),
	eventRsvps: many(eventRsvp),
	announcements: many(announcements),
	userSessions: many(userSession),
	userRoleAssignments: many(userRoleAssignment),
	messages: many(messages),
	events: many(events),
	mentorCertificates: many(mentorCertificate),
	auditLogs: many(auditLog),
	matchRuns: many(matchRun),
	matchRecommendations: many(matchRecommendation),
}));

export const tracksRelations = relations(tracks, ({one, many}) => ({
	users: many(users),
	adminScopes: many(adminScope),
	countryState: one(countryStates, {
		fields: [tracks.stateId],
		references: [countryStates.id]
	}),
	track: one(tracks, {
		fields: [tracks.parentTrackId],
		references: [tracks.id],
		relationName: "tracks_parentTrackId_tracks_id"
	}),
	tracks: many(tracks, {
		relationName: "tracks_parentTrackId_tracks_id"
	}),
	groups: many(groups),
	resources: many(resources),
	resourceAudiences: many(resourceAudience),
	announcements: many(announcements),
	announcementAudiences: many(announcementAudience),
	events: many(events),
	matchRuns: many(matchRun),
}));

export const supervisorProfileRelations = relations(supervisorProfile, ({many}) => ({
	users: many(users),
	studentProfiles: many(studentProfile),
}));

export const mentorProfileRelations = relations(mentorProfile, ({many}) => ({
	users: many(users),
	mentorInterests: many(mentorInterest),
	mentorAvailabilities: many(mentorAvailability),
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

export const countryStatesRelations = relations(countryStates, ({one, many}) => ({
	tracks: many(tracks),
	country: one(countries, {
		fields: [countryStates.countryId],
		references: [countries.id]
	}),
}));

export const countriesRelations = relations(countries, ({many}) => ({
	countryStates: many(countryStates),
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

export const mentorAvailabilityRelations = relations(mentorAvailability, ({one}) => ({
	mentorProfile: one(mentorProfile, {
		fields: [mentorAvailability.mentorUserId],
		references: [mentorProfile.userId]
	}),
}));

export const groupsRelations = relations(groups, ({one, many}) => ({
	track: one(tracks, {
		fields: [groups.trackId],
		references: [tracks.id]
	}),
	groupMemberships: many(groupMembership),
	messages: many(messages),
	matchRecommendations: many(matchRecommendation),
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
	announcementAudiences: many(announcementAudience),
	userRoleAssignments: many(userRoleAssignment),
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

export const eventsRelations = relations(events, ({one, many}) => ({
	eventRsvps: many(eventRsvp),
	user: one(users, {
		fields: [events.hostUserId],
		references: [users.id]
	}),
	track: one(tracks, {
		fields: [events.trackId],
		references: [tracks.id]
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

export const auditLogRelations = relations(auditLog, ({one}) => ({
	user: one(users, {
		fields: [auditLog.actorUserId],
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