import { pgTable, foreignKey, bigint, boolean, timestamp, varchar, unique, text, jsonb, integer, smallint, time, date, index } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



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
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "admin_scope_track_id_fkey"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "admin_scope_user_id_fkey"
		}),
]);

export const alert = pgTable("alert", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	sessionId: bigint("session_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).notNull(),
	errorReason: varchar("error_reason", { length: 255 }).notNull(),
	resolved: boolean().notNull(),
	resolvedAt: timestamp("resolved_at", { precision: 6, mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.sessionId],
			foreignColumns: [userSession.id],
			name: "alert_session_id_fkey"
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
	publishedAt: timestamp("published_at", { precision: 6, mode: 'string' }).notNull(),
	archivedAt: timestamp("archived_at", { precision: 6, mode: 'string' }),
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

export const areasOfInterest = pgTable("areas_of_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	interestDesc: varchar("interest_desc", { length: 255 }).notNull(),
}, (table) => [
	unique("areas_of_interest_interest_desc_key").on(table.interestDesc),
]);

export const countries = pgTable("countries", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	countryName: varchar("country_name", { length: 255 }).notNull(),
}, (table) => [
	unique("countries_country_name_key").on(table.countryName),
]);

export const matchRun = pgTable("match_run", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	adminUserId: text("admin_user_id").notNull(),
	runType: varchar("run_type", { length: 100 }).notNull(),
	payload: jsonb().notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).notNull(),
	result: jsonb().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.adminUserId],
			foreignColumns: [adminUser.id],
			name: "match_run_initiated_by_user_id_fkey"
		}),
]);

export const mentorProfile = pgTable("mentor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	institution: varchar({ length: 255 }),
	maxGroupCount: integer("max_group_count").notNull(),
});

export const mentorInterest = pgTable("mentor_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "mentor_interest_interest_id_fkey"
		}),
	foreignKey({
			columns: [table.mentorUserId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_interest_mentor_user_id_fkey"
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

export const events = pgTable("events", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	hostUserId: bigint("host_user_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
	eventType: varchar("event_type", { length: 100 }),
	startAt: timestamp("start_at", { precision: 6, mode: 'string' }).notNull(),
	endsAt: timestamp("ends_at", { precision: 6, mode: 'string' }).notNull(),
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

export const eventRsvp = pgTable("event_rsvp", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	rsvpStatus: varchar("rsvp_status", { length: 50 }).notNull(),
	respondedAt: timestamp("responded_at", { precision: 6, mode: 'string' }),
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

export const groups = pgTable("groups", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	groupName: varchar("group_name", { length: 255 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).notNull(),
	deletedAt: timestamp("deleted_at", { precision: 6, mode: 'string' }),
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
	joinedAt: timestamp("joined_at", { precision: 6, mode: 'string' }).notNull(),
	leftAt: timestamp("left_at", { precision: 6, mode: 'string' }),
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

export const mentorAvailability = pgTable("mentor_availability", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
	weekday: smallint().notNull(),
	startTime: time("start_time", { precision: 6 }).notNull(),
	endTime: time("end_time", { precision: 6 }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.mentorUserId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_availability_mentor_user_id_fkey"
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
	verifiedAt: timestamp("verified_at", { precision: 6, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	verifiedByUserId: bigint("verified_by_user_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.certificateTypeId],
			foreignColumns: [certificateType.id],
			name: "mentor_certificate_certificate_type_id_fkey"
		}),
	foreignKey({
			columns: [table.mentorProfileId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_certificate_mentor_profile_id_fkey"
		}),
	foreignKey({
			columns: [table.verifiedByUserId],
			foreignColumns: [users.id],
			name: "mentor_certificate_verified_by_user_id_fkey"
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
	sentAt: timestamp("sent_at", { precision: 6, mode: 'string' }).notNull(),
	editedAt: timestamp("edited_at", { precision: 6, mode: 'string' }),
	deletedAt: timestamp("deleted_at", { precision: 6, mode: 'string' }),
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

export const studentInterest = pgTable("student_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	studentUserId: bigint("student_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "student_interest_interest_id_fkey"
		}),
	foreignKey({
			columns: [table.studentUserId],
			foreignColumns: [studentProfile.userId],
			name: "student_interest_student_user_id_fkey"
		}),
]);

export const supervisorProfile = pgTable("supervisor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	schoolName: varchar("school_name", { length: 255 }).notNull(),
});

export const roles = pgTable("roles", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	slug: varchar({ length: 100 }).notNull(),
}, (table) => [
	unique("roles_slug_key").on(table.slug),
]);

export const verification = pgTable("verification", {
	id: text().primaryKey().notNull(),
	identifier: text().notNull(),
	value: text().notNull(),
	expiresAt: timestamp("expires_at", { precision: 6, mode: 'string' }).notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("verification_identifier_idx").using("btree", table.identifier.asc().nullsLast().op("text_ops")),
]);

export const adminUser = pgTable("admin_user", {
	id: text().primaryKey().notNull(),
	name: text().notNull(),
	email: text().notNull(),
	emailVerified: boolean("email_verified").default(false).notNull(),
	image: text(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	unique("user_email_key").on(table.email),
]);

export const account = pgTable("account", {
	id: text().primaryKey().notNull(),
	accountId: text("account_id").notNull(),
	providerId: text("provider_id").notNull(),
	userId: text("user_id").notNull(),
	accessToken: text("access_token"),
	refreshToken: text("refresh_token"),
	idToken: text("id_token"),
	accessTokenExpiresAt: timestamp("access_token_expires_at", { precision: 6, mode: 'string' }),
	refreshTokenExpiresAt: timestamp("refresh_token_expires_at", { precision: 6, mode: 'string' }),
	scope: text(),
	password: text(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { precision: 6, mode: 'string' }).notNull(),
}, (table) => [
	index("account_userId_idx").using("btree", table.userId.asc().nullsLast().op("text_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [adminUser.id],
			name: "account_user_id_user_id_fk"
		}).onDelete("cascade"),
]);

export const tracks = pgTable("tracks", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	trackCode: varchar("track_code", { length: 100 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	stateId: bigint("state_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.stateId],
			foreignColumns: [countryStates.id],
			name: "tracks_state_id_fkey"
		}),
	unique("tracks_track_code_key").on(table.trackCode),
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
	invitedAt: timestamp("invited_at", { precision: 6, mode: 'string' }),
	activatedAt: timestamp("activated_at", { precision: 6, mode: 'string' }),
	adminUserId: varchar("admin_user_id", { length: 255 }),
}, (table) => [
	foreignKey({
			columns: [table.adminUserId],
			foreignColumns: [adminUser.id],
			name: "users_admin_user_id_user_id_fk"
		}),
	unique("users_email_key").on(table.email),
]);

export const userSession = pgTable("user_session", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).notNull(),
	lastActivityAt: timestamp("last_activity_at", { precision: 6, mode: 'string' }),
	expiresAt: timestamp("expires_at", { precision: 6, mode: 'string' }).notNull(),
	endedAt: timestamp("ended_at", { precision: 6, mode: 'string' }),
	revokedAt: timestamp("revoked_at", { precision: 6, mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "user_session_user_id_fkey"
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
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.actorUserId],
			foreignColumns: [users.id],
			name: "audit_log_actor_user_id_fkey"
		}),
]);

export const countryStates = pgTable("country_states", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	countryId: bigint("country_id", { mode: "number" }).notNull(),
	stateName: varchar("state_name", { length: 255 }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.countryId],
			foreignColumns: [countries.id],
			name: "country_states_country_id_fkey"
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
	uploadedAt: timestamp("uploaded_at", { precision: 6, mode: 'string' }).notNull(),
	deletedAt: timestamp("deleted_at", { precision: 6, mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "resources_track_id_fkey"
		}),
	foreignKey({
			columns: [table.uploaderUserId],
			foreignColumns: [users.id],
			name: "resources_uploader_user_id_fkey"
		}),
]);

export const session = pgTable("session", {
	id: text().primaryKey().notNull(),
	expiresAt: timestamp("expires_at", { precision: 6, mode: 'string' }).notNull(),
	token: text().notNull(),
	createdAt: timestamp("created_at", { precision: 6, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { precision: 6, mode: 'string' }).notNull(),
	ipAddress: text("ip_address"),
	userAgent: text("user_agent"),
	userId: text("user_id").notNull(),
}, (table) => [
	index("session_userId_idx").using("btree", table.userId.asc().nullsLast().op("text_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [adminUser.id],
			name: "session_user_id_user_id_fk"
		}).onDelete("cascade"),
	unique("session_token_key").on(table.token),
]);

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

export const userRoleAssignment = pgTable("user_role_assignment", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }).notNull(),
	validFrom: timestamp("valid_from", { precision: 6, mode: 'string' }).notNull(),
	validTo: timestamp("valid_to", { precision: 6, mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "user_role_assignment_role_id_fkey"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "user_role_assignment_user_id_fkey"
		}),
]);
