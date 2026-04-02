import { pgTable, unique, bigint, varchar, foreignKey, boolean, timestamp, uniqueIndex, integer, smallint, time, text, date, jsonb, numeric } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



export const roles = pgTable("roles", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	slug: varchar({ length: 100 }).notNull(),
}, (table) => [
	unique("roles_slug_key").on(table.slug),
]);

export const studentInterest = pgTable("student_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	studentUserId: bigint("student_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.studentUserId],
			foreignColumns: [studentProfile.userId],
			name: "student_interest_student_user_id_fkey"
		}),
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "student_interest_interest_id_fkey"
		}),
]);

export const users = pgTable("users", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	email: varchar({ length: 255 }).notNull(),
	firstName: varchar("first_name", { length: 255 }).notNull(),
	lastName: varchar("last_name", { length: 255 }).notNull(),
	isActive: boolean("is_active").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }).notNull(),
	accountStatus: varchar("account_status", { length: 50 }).notNull(),
	invitedAt: timestamp("invited_at", { mode: 'string' }),
	activatedAt: timestamp("activated_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "users_track_id_fkey"
		}),
	foreignKey({
			columns: [table.id],
			foreignColumns: [supervisorProfile.userId],
			name: "users_id_fkey"
		}),
	foreignKey({
			columns: [table.id],
			foreignColumns: [mentorProfile.userId],
			name: "users_id_fkey1"
		}),
	foreignKey({
			columns: [table.id],
			foreignColumns: [studentProfile.userId],
			name: "users_id_fkey2"
		}),
	unique("users_email_key").on(table.email),
]);

export const adminScope = pgTable("admin_scope", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	isGlobal: boolean("is_global").notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "admin_scope_user_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "admin_scope_track_id_fkey"
		}),
]);

export const tracks = pgTable("tracks", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	trackCode: varchar("track_code", { length: 100 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	stateId: bigint("state_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	parentTrackId: bigint("parent_track_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.stateId],
			foreignColumns: [countryStates.id],
			name: "tracks_state_id_fkey"
		}),
	foreignKey({
			columns: [table.parentTrackId],
			foreignColumns: [table.id],
			name: "tracks_parent_track_id_fkey"
		}),
	unique("tracks_track_code_key").on(table.trackCode),
]);

export const countries = pgTable("countries", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	countryName: varchar("country_name", { length: 255 }).notNull(),
}, (table) => [
	unique("countries_country_name_key").on(table.countryName),
]);

export const countryStates = pgTable("country_states", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	countryId: bigint("country_id", { mode: "number" }).notNull(),
	stateName: varchar("state_name", { length: 255 }).notNull(),
}, (table) => [
	uniqueIndex("country_states_country_id_state_name_idx").using("btree", table.countryId.asc().nullsLast().op("int8_ops"), table.stateName.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.countryId],
			foreignColumns: [countries.id],
			name: "country_states_country_id_fkey"
		}),
]);

export const supervisorProfile = pgTable("supervisor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	schoolName: varchar("school_name", { length: 255 }).notNull(),
});

export const mentorProfile = pgTable("mentor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	institution: varchar({ length: 255 }),
	maxGroupCount: integer("max_group_count").notNull(),
});

export const studentProfile = pgTable("student_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	supervisorUserId: bigint("supervisor_user_id", { mode: "number" }),
	schoolName: varchar("school_name", { length: 255 }),
	yearLevel: smallint("year_level"),
	joinPermissionReceived: boolean("join_permission_received").notNull(),
	joinPermissionResponseId: varchar("join_permission_response_id", { length: 255 }),
}, (table) => [
	foreignKey({
			columns: [table.supervisorUserId],
			foreignColumns: [supervisorProfile.userId],
			name: "student_profile_supervisor_user_id_fkey"
		}),
]);

export const areasOfInterest = pgTable("areas_of_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	interestDesc: varchar("interest_desc", { length: 255 }).notNull(),
}, (table) => [
	unique("areas_of_interest_interest_desc_key").on(table.interestDesc),
]);

export const mentorInterest = pgTable("mentor_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }).notNull(),
}, (table) => [
	uniqueIndex("mentor_interest_mentor_user_id_interest_id_idx").using("btree", table.mentorUserId.asc().nullsLast().op("int8_ops"), table.interestId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.mentorUserId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_interest_mentor_user_id_fkey"
		}),
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "mentor_interest_interest_id_fkey"
		}),
]);

export const mentorAvailability = pgTable("mentor_availability", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
	weekday: smallint().notNull(),
	startTime: time("start_time").notNull(),
	endTime: time("end_time").notNull(),
}, (table) => [
	uniqueIndex("mentor_availability_mentor_user_id_weekday_start_time_end_t_idx").using("btree", table.mentorUserId.asc().nullsLast().op("int2_ops"), table.weekday.asc().nullsLast().op("time_ops"), table.startTime.asc().nullsLast().op("int8_ops"), table.endTime.asc().nullsLast().op("time_ops")),
	foreignKey({
			columns: [table.mentorUserId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_availability_mentor_user_id_fkey"
		}),
]);

export const groups = pgTable("groups", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	groupName: varchar("group_name", { length: 255 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { mode: 'string' }).notNull(),
	deletedAt: timestamp("deleted_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "groups_track_id_fkey"
		}),
]);

export const groupMembership = pgTable("group_membership", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	membershipRole: varchar("membership_role", { length: 50 }),
	joinedAt: timestamp("joined_at", { mode: 'string' }).notNull(),
	leftAt: timestamp("left_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "group_membership_group_id_fkey"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "group_membership_user_id_fkey"
		}),
]);

export const resources = pgTable("resources", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	uploaderUserId: bigint("uploader_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	visibilityScope: varchar("visibility_scope", { length: 50 }).notNull(),
	uploadedAt: timestamp("uploaded_at", { mode: 'string' }).notNull(),
	deletedAt: timestamp("deleted_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.uploaderUserId],
			foreignColumns: [users.id],
			name: "resources_uploader_user_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "resources_track_id_fkey"
		}),
]);

export const resourceAudience = pgTable("resource_audience", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	resourceId: bigint("resource_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.resourceId],
			foreignColumns: [resources.id],
			name: "resource_audience_resource_id_fkey"
		}),
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "resource_audience_role_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "resource_audience_track_id_fkey"
		}),
]);

export const eventRsvp = pgTable("event_rsvp", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	rsvpStatus: varchar("rsvp_status", { length: 50 }).notNull(),
	respondedAt: timestamp("responded_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.eventId],
			foreignColumns: [events.id],
			name: "event_rsvp_event_id_fkey"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "event_rsvp_user_id_fkey"
		}),
]);

export const announcements = pgTable("announcements", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	authorUserId: bigint("author_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	visibilityScope: varchar("visibility_scope", { length: 50 }).notNull(),
	publishedAt: timestamp("published_at", { mode: 'string' }).notNull(),
	archivedAt: timestamp("archived_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.authorUserId],
			foreignColumns: [users.id],
			name: "announcements_author_user_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "announcements_track_id_fkey"
		}),
]);

export const announcementAudience = pgTable("announcement_audience", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	announcementId: bigint("announcement_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.announcementId],
			foreignColumns: [announcements.id],
			name: "announcement_audience_announcement_id_fkey"
		}),
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "announcement_audience_role_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "announcement_audience_track_id_fkey"
		}),
]);

export const certificateType = pgTable("certificate_type", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	name: varchar({ length: 255 }).notNull(),
	requiresNumber: boolean("requires_number").notNull(),
	requiresExpiry: boolean("requires_expiry").notNull(),
}, (table) => [
	unique("certificate_type_name_key").on(table.name),
]);

export const userSession = pgTable("user_session", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { mode: 'string' }).notNull(),
	lastActivityAt: timestamp("last_activity_at", { mode: 'string' }),
	expiresAt: timestamp("expires_at", { mode: 'string' }).notNull(),
	endedAt: timestamp("ended_at", { mode: 'string' }),
	revokedAt: timestamp("revoked_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "user_session_user_id_fkey"
		}),
]);

export const alert = pgTable("alert", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	sessionId: bigint("session_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { mode: 'string' }).notNull(),
	errorReason: varchar("error_reason", { length: 255 }).notNull(),
	resolved: boolean().notNull(),
	resolvedAt: timestamp("resolved_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.sessionId],
			foreignColumns: [userSession.id],
			name: "alert_session_id_fkey"
		}),
]);

export const userRoleAssignment = pgTable("user_role_assignment", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }).notNull(),
	validFrom: timestamp("valid_from", { mode: 'string' }).notNull(),
	validTo: timestamp("valid_to", { mode: 'string' }),
}, (table) => [
	uniqueIndex("user_role_assignment_user_id_role_id_valid_from_idx").using("btree", table.userId.asc().nullsLast().op("int8_ops"), table.roleId.asc().nullsLast().op("int8_ops"), table.validFrom.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "user_role_assignment_user_id_fkey"
		}),
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "user_role_assignment_role_id_fkey"
		}),
]);

export const messages = pgTable("messages", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	senderUserId: bigint("sender_user_id", { mode: "number" }).notNull(),
	messageText: text("message_text").notNull(),
	sentAt: timestamp("sent_at", { mode: 'string' }).notNull(),
	editedAt: timestamp("edited_at", { mode: 'string' }),
	deletedAt: timestamp("deleted_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "messages_group_id_fkey"
		}),
	foreignKey({
			columns: [table.senderUserId],
			foreignColumns: [users.id],
			name: "messages_sender_user_id_fkey"
		}),
]);

export const events = pgTable("events", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	hostUserId: bigint("host_user_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	eventType: varchar("event_type", { length: 100 }),
	startAt: timestamp("start_at", { mode: 'string' }).notNull(),
	endsAt: timestamp("ends_at", { mode: 'string' }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.hostUserId],
			foreignColumns: [users.id],
			name: "events_host_user_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "events_track_id_fkey"
		}),
]);

export const mentorCertificate = pgTable("mentor_certificate", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorProfileId: bigint("mentor_profile_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	certificateTypeId: bigint("certificate_type_id", { mode: "number" }).notNull(),
	certificateNumber: varchar("certificate_number", { length: 255 }),
	issuedBy: varchar("issued_by", { length: 255 }),
	issuedAt: date("issued_at").notNull(),
	expiresAt: date("expires_at"),
	fileUrl: varchar("file_url", { length: 500 }),
	verifiedAt: timestamp("verified_at", { mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	verifiedByUserId: bigint("verified_by_user_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.mentorProfileId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_certificate_mentor_profile_id_fkey"
		}),
	foreignKey({
			columns: [table.certificateTypeId],
			foreignColumns: [certificateType.id],
			name: "mentor_certificate_certificate_type_id_fkey"
		}),
	foreignKey({
			columns: [table.verifiedByUserId],
			foreignColumns: [users.id],
			name: "mentor_certificate_verified_by_user_id_fkey"
		}),
]);

export const auditLog = pgTable("audit_log", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	actorUserId: bigint("actor_user_id", { mode: "number" }),
	entityType: varchar("entity_type", { length: 100 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	entityId: bigint("entity_id", { mode: "number" }).notNull(),
	action: varchar({ length: 100 }).notNull(),
	beforeState: jsonb("before_state"),
	afterState: jsonb("after_state"),
	createdAt: timestamp("created_at", { mode: 'string' }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.actorUserId],
			foreignColumns: [users.id],
			name: "audit_log_actor_user_id_fkey"
		}),
]);

export const matchRun = pgTable("match_run", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	initiatedByUserId: bigint("initiated_by_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	runType: varchar("run_type", { length: 100 }).notNull(),
	rulesSnapshot: jsonb("rules_snapshot"),
	createdAt: timestamp("created_at", { mode: 'string' }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.initiatedByUserId],
			foreignColumns: [users.id],
			name: "match_run_initiated_by_user_id_fkey"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "match_run_track_id_fkey"
		}),
]);

export const matchRecommendation = pgTable("match_recommendation", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	matchRunId: bigint("match_run_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
	score: numeric({ precision: 10, scale:  4 }),
	explanation: jsonb(),
	accepted: boolean().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.matchRunId],
			foreignColumns: [matchRun.id],
			name: "match_recommendation_match_run_id_fkey"
		}),
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "match_recommendation_group_id_fkey"
		}),
	foreignKey({
			columns: [table.mentorUserId],
			foreignColumns: [users.id],
			name: "match_recommendation_mentor_user_id_fkey"
		}),
]);
