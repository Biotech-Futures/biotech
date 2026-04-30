import { pgTable, index, foreignKey, check, bigint, varchar, timestamp, boolean, pgSchema, text, unique, integer, interval, jsonb, serial, smallint, date } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"

export const events = pgTable("events", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "events_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	eventName: varchar("event_name", { length: 255 }).notNull(),
	description: varchar({ length: 255 }),
	startDatetime: timestamp("start_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	endsDatetime: timestamp("ends_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	location: varchar({ length: 255 }),
	humanitixLink: varchar("humanitix_link", { length: 255 }).notNull(),
	deletedFlag: boolean("deleted_flag").notNull(),
	deletedDatetime: timestamp("deleted_datetime", { withTimezone: true, mode: 'string' }),
	"eventImage(img)": varchar("event_image(IMG)", { length: 255 }),
	isVirtual: boolean("is_virtual").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	hostUserId: bigint("host_user_id", { mode: "number" }),
}, (table) => [
	index("events_host_us_34c951_idx").using("btree", table.hostUserId.asc().nullsLast().op("int8_ops")),
	index("events_host_user_id_f7fc239c").using("btree", table.hostUserId.asc().nullsLast().op("int8_ops")),
	index("events_start_d_2ddaa0_idx").using("btree", table.startDatetime.asc().nullsLast().op("timestamptz_ops")),
	foreignKey({
			columns: [table.hostUserId],
			foreignColumns: [users.id],
			name: "events_host_user_id_f7fc239c_fk_users_id"
		}),
	check("check_deleted_flag_and_datetime", sql`(NOT deleted_flag) OR (deleted_flag AND (deleted_datetime IS NOT NULL))`),
	check("check_event_end_after_start", sql`ends_datetime > start_datetime`),
	check("check_virtual_location_null", sql`(NOT is_virtual) OR (location IS NULL)`),
]);

export const users = pgTable("users", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "users_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	password: varchar({ length: 128 }).notNull(),
	lastLogin: timestamp("last_login", { withTimezone: true, mode: 'string' }),
	isSuperuser: boolean("is_superuser").notNull(),
	firstName: varchar("first_name", { length: 255 }).notNull(),
	lastName: varchar("last_name", { length: 255 }).notNull(),
	isStaff: boolean("is_staff").notNull(),
	isActive: boolean("is_active").notNull(),
	dateJoined: timestamp("date_joined", { withTimezone: true, mode: 'string' }).notNull(),
	email: varchar({ length: 254 }).notNull(),
	status: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	stateId: bigint("state_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.stateId],
			foreignColumns: [countryStates.id],
			name: "users_state_id_0521d641_fk_country_states_id"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "users_track_id_e7963e8d_fk_tracks_id"
		}),
	unique("users_email_key").on(table.email),
]);

export const djangoContentType = pgTable("django_content_type", {
	id: integer().primaryKey().generatedByDefaultAsIdentity({ name: "django_content_type_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 2147483647, cache: 1 }),
	appLabel: varchar("app_label", { length: 100 }).notNull(),
	model: varchar({ length: 100 }).notNull(),
}, (table) => [
	unique("django_content_type_app_label_model_76bd3d3b_uniq").on(table.appLabel, table.model),
]);

export const countryStates = pgTable("country_states", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "country_states_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	stateName: varchar("state_name", { length: 255 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	countryId: bigint("country_id", { mode: "number" }).notNull(),
}, (table) => [
	index("country_states_country_id_c84f5fb5").using("btree", table.countryId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.countryId],
			foreignColumns: [countries.id],
			name: "country_states_country_id_c84f5fb5_fk_countries_id"
		}),
	unique("unique_state_per_country").on(table.stateName, table.countryId),
]);

export const usersGroups = pgTable("users_groups", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "users_groups_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	groupId: integer("group_id").notNull(),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [authGroup.id],
			name: "users_groups_group_id_2f3517aa_fk_auth_group_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "users_groups_user_id_f500bee5_fk_users_id"
		}),
	unique("users_groups_user_id_group_id_fc7788e8_uniq").on(table.userId, table.groupId),
]);

export const usersUserPermissions = pgTable("users_user_permissions", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "users_user_permissions_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	permissionId: integer("permission_id").notNull(),
}, (table) => [
	foreignKey({
			columns: [table.permissionId],
			foreignColumns: [authPermission.id],
			name: "users_user_permissio_permission_id_6d08dcd2_fk_auth_perm"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "users_user_permissions_user_id_92473840_fk_users_id"
		}),
	unique("users_user_permissions_user_id_permission_id_3b86cbdf_uniq").on(table.userId, table.permissionId),
]);

export const workshopAttendance = pgTable("workshop_attendance", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "workshop_attendance_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	responded: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	workshopId: bigint("workshop_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "workshop_attendance_user_id_c7587c90_fk_users_id"
		}),
	foreignKey({
			columns: [table.workshopId],
			foreignColumns: [workshops.workshopId],
			name: "workshop_attendance_workshop_id_15b47095_fk_workshops"
		}),
	unique("pk_workshop_attendance").on(table.userId, table.workshopId),
]);

export const workshops = pgTable("workshops", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	workshopId: bigint("workshop_id", { mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "workshops_workshop_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	workshopName: varchar("workshop_name", { length: 255 }).notNull(),
	startDatetime: timestamp("start_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	duration: interval().notNull(),
	location: varchar({ length: 255 }).notNull(),
	description: varchar({ length: 255 }),
	zoomLink: varchar("zoom_link", { length: 255 }),
	deletedFlag: boolean("deleted_flag").notNull(),
	deletedDatetime: timestamp("deleted_datetime", { withTimezone: true, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	hostUserId: bigint("host_user_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "workshops_group_id_452b7f33_fk_groups_id"
		}),
	foreignKey({
			columns: [table.hostUserId],
			foreignColumns: [users.id],
			name: "workshops_host_user_id_c0c274b0_fk_users_id"
		}),
]);

export const resources = pgTable("resources", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "resources_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	name: varchar({ length: 255 }).notNull(),
	description: varchar({ length: 255 }).notNull(),
	uploadedAt: timestamp("uploaded_at", { withTimezone: true, mode: 'string' }).notNull(),
	deletedAt: timestamp("deleted_at", { withTimezone: true, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	uploadedById: bigint("uploaded_by_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	typeId: bigint("type_id", { mode: "number" }),
	fileMimeType: varchar("file_mime_type", { length: 100 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	fileSize: bigint("file_size", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }),
	kind: varchar({ length: 20 }).default('file').notNull(),
	storageKey: varchar("storage_key", { length: 500 }),
	visibilityScope: varchar("visibility_scope", { length: 50 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
}, (table) => [
	index("resources_group_id_idx").using("btree", table.groupId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "resources_group_id_5680e4d8_fk_groups_id"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "resources_track_id_c4079c5a_fk_tracks_id"
		}),
	foreignKey({
			columns: [table.typeId],
			foreignColumns: [resourceTypes.id],
			name: "resources_type_id_93682dd6_fk_resource_types_id"
		}),
	foreignKey({
			columns: [table.uploadedById],
			foreignColumns: [users.id],
			name: "resources_uploaded_by_id_918d19f2_fk_users_id"
		}),
	check("deleted_after_upload", sql`(deleted_at >= uploaded_at) OR (deleted_at IS NULL)`),
	check("resource_description_not_empty", sql`NOT ((description)::text = ''::text)`),
	check("resource_upload_not_future", sql`uploaded_at <= statement_timestamp()`),
]);

export const resourceAudience = pgTable("resource_audience", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "resource_roles_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	resourceId: bigint("resource_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.resourceId],
			foreignColumns: [resources.id],
			name: "resource_audience_resource_id_4a807083_fk_resources_id"
		}),
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "resource_audience_role_id_34580b4e_fk_roles_id"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "resource_audience_track_id_8c2cfbea_fk_tracks_id"
		}),
	unique("pk_resource_role").on(table.resourceId, table.roleId),
]);

export const adminProfile = pgTable("admin_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	adminId: bigint("admin_id", { mode: "number" }).primaryKey().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.adminId],
			foreignColumns: [users.id],
			name: "admin_profile_admin_id_d55c5f00_fk_users_id"
		}),
]);

export const alerts = pgTable("alerts", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "alerts_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	alertTimestamp: timestamp("alert_timestamp", { withTimezone: true, mode: 'string' }).notNull(),
	errorReason: varchar("error_reason", { length: 255 }).notNull(),
	resolved: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	sessionId: bigint("session_id", { mode: "number" }).notNull(),
}, (table) => [
	index("alerts_alert_t_e3b260_idx").using("btree", table.alertTimestamp.asc().nullsLast().op("timestamptz_ops")),
	index("alerts_resolve_915a53_idx").using("btree", table.resolved.asc().nullsLast().op("bool_ops")),
	index("alerts_session_6b4a0a_idx").using("btree", table.sessionId.asc().nullsLast().op("int8_ops")),
	index("alerts_session_id_286fb9cc").using("btree", table.sessionId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.sessionId],
			foreignColumns: [sessions.id],
			name: "alerts_session_id_286fb9cc_fk_sessions_id"
		}),
	unique("unique_alert_user_session").on(table.alertTimestamp, table.errorReason, table.sessionId),
	check("alert_reason_not_empty", sql`NOT ((error_reason)::text = ''::text)`),
]);

export const authPermission = pgTable("auth_permission", {
	id: integer().primaryKey().generatedByDefaultAsIdentity({ name: "auth_permission_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 2147483647, cache: 1 }),
	name: varchar({ length: 255 }).notNull(),
	contentTypeId: integer("content_type_id").notNull(),
	codename: varchar({ length: 100 }).notNull(),
}, (table) => [
	index("auth_permission_content_type_id_2f476e4b").using("btree", table.contentTypeId.asc().nullsLast().op("int4_ops")),
	foreignKey({
			columns: [table.contentTypeId],
			foreignColumns: [djangoContentType.id],
			name: "auth_permission_content_type_id_2f476e4b_fk_django_co"
		}),
	unique("auth_permission_content_type_id_codename_01ab375a_uniq").on(table.contentTypeId, table.codename),
]);

export const authGroupPermissions = pgTable("auth_group_permissions", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "auth_group_permissions_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	groupId: integer("group_id").notNull(),
	permissionId: integer("permission_id").notNull(),
}, (table) => [
	index("auth_group_permissions_group_id_b120cbf9").using("btree", table.groupId.asc().nullsLast().op("int4_ops")),
	index("auth_group_permissions_permission_id_84c5c92e").using("btree", table.permissionId.asc().nullsLast().op("int4_ops")),
	foreignKey({
			columns: [table.permissionId],
			foreignColumns: [authPermission.id],
			name: "auth_group_permissio_permission_id_84c5c92e_fk_auth_perm"
		}),
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [authGroup.id],
			name: "auth_group_permissions_group_id_b120cbf9_fk_auth_group_id"
		}),
	unique("auth_group_permissions_group_id_permission_id_0cd325b0_uniq").on(table.groupId, table.permissionId),
]);

export const authGroup = pgTable("auth_group", {
	id: integer().primaryKey().generatedByDefaultAsIdentity({ name: "auth_group_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 2147483647, cache: 1 }),
	name: varchar({ length: 150 }).notNull(),
}, (table) => [
	index("auth_group_name_a6ea08ec_like").using("btree", table.name.asc().nullsLast().op("varchar_pattern_ops")),
	unique("auth_group_name_key").on(table.name),
]);

export const areasOfInterest = pgTable("areas_of_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "areas_of_interest_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	interestDesc: varchar("interest_desc", { length: 255 }).notNull(),
});

export const eventTargetGroup = pgTable("event_target_group", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "event_target_group_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
}, (table) => [
	index("event_targe_event_i_d53a84_idx").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_targe_group_i_29198c_idx").using("btree", table.groupId.asc().nullsLast().op("int8_ops")),
	index("event_target_group_event_id_3102faf9").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_target_group_group_id_9b0af69c").using("btree", table.groupId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.eventId],
			foreignColumns: [events.id],
			name: "event_target_group_event_id_3102faf9_fk_events_id"
		}),
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "event_target_group_group_id_9b0af69c_fk_groups_id"
		}),
	unique("unique_event_group").on(table.eventId, table.groupId),
]);

export const eventInvite = pgTable("event_invite", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "event_invite_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	sentDatetime: timestamp("sent_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	attendanceStatus: boolean("attendance_status").notNull(),
	rsvpStatus: boolean("rsvp_status").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
}, (table) => [
	index("event_invit_event_i_c093b3_idx").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_invit_user_id_db0358_idx").using("btree", table.userId.asc().nullsLast().op("int8_ops")),
	index("event_invite_event_id_d0229d7f").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_invite_user_id_5c26a2a6").using("btree", table.userId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.eventId],
			foreignColumns: [events.id],
			name: "event_invite_event_id_d0229d7f_fk_events_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "event_invite_user_id_5c26a2a6_fk_users_id"
		}),
	unique("unique_event_user").on(table.userId, table.eventId),
	check("check_attendance_requires_rsvp", sql`(NOT attendance_status) OR rsvp_status`),
	check("check_invite_sent_datetime_not_future", sql`sent_datetime <= statement_timestamp()`),
]);

export const djangoMigrations = pgTable("django_migrations", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "django_migrations_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	app: varchar({ length: 255 }).notNull(),
	name: varchar({ length: 255 }).notNull(),
	applied: timestamp({ withTimezone: true, mode: 'string' }).notNull(),
});

export const djangoSession = pgTable("django_session", {
	sessionKey: varchar("session_key", { length: 40 }).primaryKey().notNull(),
	sessionData: text("session_data").notNull(),
	expireDate: timestamp("expire_date", { withTimezone: true, mode: 'string' }).notNull(),
}, (table) => [
	index("django_session_expire_date_a5c62663").using("btree", table.expireDate.asc().nullsLast().op("timestamptz_ops")),
	index("django_session_session_key_c0390e0f_like").using("btree", table.sessionKey.asc().nullsLast().op("varchar_pattern_ops")),
]);

export const countries = pgTable("countries", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "countries_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	countryName: varchar("country_name", { length: 255 }).notNull(),
}, (table) => [
	index("countries_country_6f41c3_idx").using("btree", table.countryName.asc().nullsLast().op("text_ops")),
]);

export const djangoAdminLog = pgTable("django_admin_log", {
	id: integer().primaryKey().generatedByDefaultAsIdentity({ name: "django_admin_log_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 2147483647, cache: 1 }),
	actionTime: timestamp("action_time", { withTimezone: true, mode: 'string' }).notNull(),
	objectId: text("object_id"),
	objectRepr: varchar("object_repr", { length: 200 }).notNull(),
	actionFlag: smallint("action_flag").notNull(),
	changeMessage: text("change_message").notNull(),
	contentTypeId: integer("content_type_id"),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
}, (table) => [
	index("django_admin_log_content_type_id_c4bce8eb").using("btree", table.contentTypeId.asc().nullsLast().op("int4_ops")),
	index("django_admin_log_user_id_c564eba6").using("btree", table.userId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.contentTypeId],
			foreignColumns: [djangoContentType.id],
			name: "django_admin_log_content_type_id_c4bce8eb_fk_django_co"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "django_admin_log_user_id_c564eba6_fk_users_id"
		}),
	check("django_admin_log_action_flag_check", sql`action_flag >= 0`),
]);

export const eventTargetRole = pgTable("event_target_role", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "event_target_role_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }).notNull(),
}, (table) => [
	index("event_target_role_event_id_62145d19").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_target_role_role_id_f7baea72").using("btree", table.roleId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.eventId],
			foreignColumns: [events.id],
			name: "event_target_role_event_id_62145d19_fk_events_id"
		}),
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "event_target_role_role_id_f7baea72_fk_roles_id"
		}),
	unique("unique_event_role").on(table.eventId, table.roleId),
]);

export const certificateType = pgTable("certificate_type", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "certificate_type_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	certificateType: varchar("certificate_type", { length: 255 }).notNull(),
	requiresNumber: boolean("requires_number").notNull(),
	requiresExpiry: boolean("requires_expiry").notNull(),
}, (table) => [
	index("certificate_certifi_187256_idx").using("btree", table.certificateType.asc().nullsLast().op("text_ops")),
	index("certificate_type_certificate_type_dc054d41_like").using("btree", table.certificateType.asc().nullsLast().op("varchar_pattern_ops")),
	unique("certificate_type_certificate_type_key").on(table.certificateType),
]);

export const background = pgTable("background", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "background_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	backgroundDescUniqueField: text("background_desc_unique_field").notNull(),
});

export const groups = pgTable("groups", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "groups_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	groupName: varchar("group_name", { length: 255 }).notNull(),
	creationDatetime: timestamp("creation_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	deletedFlag: boolean("deleted_flag").notNull(),
	deletedDatetime: timestamp("deleted_datetime", { withTimezone: true, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }).notNull(),
}, (table) => [
	index("groups_creatio_f6499a_idx").using("btree", table.creationDatetime.asc().nullsLast().op("timestamptz_ops")),
	index("groups_deleted_f0201e_idx").using("btree", table.deletedFlag.asc().nullsLast().op("bool_ops")),
	index("groups_track_i_093220_idx").using("btree", table.trackId.asc().nullsLast().op("int8_ops")),
	index("groups_track_id_f29fde9a").using("btree", table.trackId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "groups_track_id_f29fde9a_fk_tracks_id"
		}),
	unique("unique_group_name_per_track").on(table.groupName, table.trackId),
	check("deleted_after_creation", sql`(deleted_datetime >= creation_datetime) OR (deleted_datetime IS NULL)`),
	check("group_creation_not_future", sql`creation_datetime <= statement_timestamp()`),
	check("group_deleted_flag_datetime_consistent", sql`(deleted_flag AND (deleted_datetime IS NOT NULL)) OR ((NOT deleted_flag) AND (deleted_datetime IS NULL))`),
	check("group_name_not_empty", sql`NOT ((group_name)::text ~ '^s*$'::text)`),
]);

export const eventTargetTrack = pgTable("event_target_track", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "event_target_track_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	eventId: bigint("event_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	trackId: bigint("track_id", { mode: "number" }).notNull(),
}, (table) => [
	index("event_target_track_event_id_d4858886").using("btree", table.eventId.asc().nullsLast().op("int8_ops")),
	index("event_target_track_track_id_1163cca1").using("btree", table.trackId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.eventId],
			foreignColumns: [events.id],
			name: "event_target_track_event_id_d4858886_fk_events_id"
		}),
	foreignKey({
			columns: [table.trackId],
			foreignColumns: [tracks.id],
			name: "event_target_track_track_id_1163cca1_fk_tracks_id"
		}),
	unique("unique_event_track").on(table.eventId, table.trackId),
]);

export const messageResources = pgTable("message_resources", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "message_resources_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	messageId: bigint("message_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	resourceId: bigint("resource_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.messageId],
			foreignColumns: [messages.id],
			name: "message_resources_message_id_e0b74b54_fk_messages_id"
		}),
	foreignKey({
			columns: [table.resourceId],
			foreignColumns: [resources.id],
			name: "message_resources_resource_id_7bf8fbc9_fk_resources_id"
		}),
	unique("message_resources_message_id_resource_id_9a04fab7_uniq").on(table.messageId, table.resourceId),
]);

export const mentorProfile = pgTable("mentor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	institution: varchar("Institution", { length: 255 }).notNull(),
	mentorReason: varchar("mentor_reason", { length: 255 }).notNull(),
	maxGrpCnt: integer("max_grp_cnt").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	backgroundId: bigint("background_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.backgroundId],
			foreignColumns: [background.id],
			name: "mentor_profile_background_id_000edd98_fk_background_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "mentor_profile_user_id_a4034c13_fk_users_id"
		}),
	check("mentor_max_grp_non_negative", sql`max_grp_cnt >= 0`),
]);

export const messageAttachments = pgTable("message_attachments", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "message_attachments_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	attachmentId: varchar("attachment_id", { length: 255 }).notNull(),
	attachmentFilename: varchar("attachment_filename", { length: 255 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	messageId: bigint("message_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.messageId],
			foreignColumns: [messages.id],
			name: "message_attachments_message_id_c7a3e22d_fk_messages_id"
		}),
	unique("message_attachments_attachment_id_key").on(table.attachmentId),
	unique("unique_filename_per_message").on(table.attachmentFilename, table.messageId),
]);

export const groupMembers = pgTable("group_members", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "group_members_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
}, (table) => [
	index("group_membe_group_i_d2cebc_idx").using("btree", table.groupId.asc().nullsLast().op("int8_ops")),
	index("group_membe_user_id_88c209_idx").using("btree", table.userId.asc().nullsLast().op("int8_ops")),
	index("group_members_group_id_68d06a36").using("btree", table.groupId.asc().nullsLast().op("int8_ops")),
	index("group_members_user_id_cffc0595").using("btree", table.userId.asc().nullsLast().op("int8_ops")),
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "group_members_group_id_68d06a36_fk_groups_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "group_members_user_id_cffc0595_fk_users_id"
		}),
	unique("unique_group_user").on(table.userId, table.groupId),
]);

export const loginTokens = pgTable("login_tokens", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "login_tokens_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	token: varchar({ length: 6 }).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).notNull(),
	expiresAt: timestamp("expires_at", { withTimezone: true, mode: 'string' }).notNull(),
	used: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
}, (table) => [
	index("login_token_created_7a566c_idx").using("btree", table.createdAt.asc().nullsLast().op("timestamptz_ops")),
	index("login_token_expires_133cb3_idx").using("btree", table.expiresAt.asc().nullsLast().op("timestamptz_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "login_tokens_user_id_7f12777f_fk_users_id"
		}),
]);

export const mentorCertificate = pgTable("mentor_certificate", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "mentor_certificate_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	certificateNumber: varchar("certificate_number", { length: 255 }),
	issuedBy: varchar("issued_by", { length: 255 }).notNull(),
	issuedAt: date("issued_at").notNull(),
	expiresAt: date("expires_at"),
	fileUrl: varchar("file_url", { length: 500 }),
	verified: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	certificateTypeId: bigint("certificate_type_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	mentorProfileId: bigint("mentor_profile_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.certificateTypeId],
			foreignColumns: [certificateType.id],
			name: "mentor_certificate_certificate_type_id_090af26f_fk_certifica"
		}),
	foreignKey({
			columns: [table.mentorProfileId],
			foreignColumns: [mentorProfile.userId],
			name: "mentor_certificate_mentor_profile_id_61bbc118_fk_mentor_pr"
		}),
	unique("unique_certificate_per_mentor").on(table.certificateNumber, table.certificateTypeId, table.mentorProfileId),
	check("cannot_verify_expired_certificate", sql`(expires_at IS NULL) OR (expires_at >= statement_timestamp()) OR (NOT verified)`),
]);

export const messageStatus = pgTable("message_status", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "message_status_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	status: varchar({ length: 20 }).notNull(),
	deliveredAt: timestamp("delivered_at", { withTimezone: true, mode: 'string' }),
	readAt: timestamp("read_at", { withTimezone: true, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	messageId: bigint("message_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.messageId],
			foreignColumns: [messages.id],
			name: "message_status_message_id_7d8e74e7_fk_messages_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "message_status_user_id_0673798e_fk_users_id"
		}),
	unique("message_status_message_id_user_id_e0eb32f9_uniq").on(table.messageId, table.userId),
]);

export const roles = pgTable("roles", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "roles_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	roleName: varchar("role_name", { length: 255 }).notNull(),
}, (table) => [
	unique("roles_role_name_key").on(table.roleName),
	check("role_name_not_empty", sql`NOT ((role_name)::text = ''::text)`),
]);

export const milestone = pgTable("milestone", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "milestone_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	milestoneName: varchar("milestone_name", { length: 255 }).notNull(),
	completed: boolean().notNull(),
	deletedFlag: boolean("deleted_flag").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "milestone_group_id_11a6a79d_fk_groups_id"
		}),
]);

export const studentInterest = pgTable("student_interest", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "student_interest_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "student_interest_interest_id_7f538900_fk_areas_of_interest_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "student_interest_user_id_a32699eb_fk_users_id"
		}),
	unique("pk_student_interest").on(table.interestId, table.userId),
]);

export const messages = pgTable("messages", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "messages_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	messageText: text("message_text").notNull(),
	sentAt: timestamp("sent_at", { withTimezone: true, mode: 'string' }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	groupId: bigint("group_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	senderUserId: bigint("sender_user_id", { mode: "number" }).notNull(),
	editedAt: timestamp("edited_at", { withTimezone: true, mode: 'string' }),
	deletedAt: timestamp("deleted_at", { withTimezone: true, mode: 'string' }),
	messageType: varchar("message_type", { length: 20 }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.groupId],
			foreignColumns: [groups.id],
			name: "messages_group_id_0fd96228_fk_groups_id"
		}),
	foreignKey({
			columns: [table.senderUserId],
			foreignColumns: [users.id],
			name: "messages_sender_user_id_b1b10099_fk_users_id"
		}),
	check("message_deleted_after_sent", sql`(deleted_at IS NULL) OR (deleted_at >= sent_at)`),
	check("message_edited_after_sent", sql`(edited_at IS NULL) OR (edited_at >= sent_at)`),
]);

export const sessions = pgTable("sessions", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "sessions_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	accessDatetime: timestamp("access_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	isLoggedin: boolean().notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "sessions_user_id_05e26f4a_fk_users_id"
		}),
	unique("unique_user_session").on(table.accessDatetime, table.userId),
	check("access_not_in_future", sql`access_datetime <= statement_timestamp()`),
]);

export const resourceTypes = pgTable("resource_types", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "resource_types_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	name: varchar({ length: 50 }).notNull(),
	description: varchar({ length: 255 }),
}, (table) => [
	unique("resource_types_type_name_key").on(table.name),
]);

export const roleAssignmentHistory = pgTable("role_assignment_history", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "role_assignment_history_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	validFrom: timestamp("valid_from", { withTimezone: true, mode: 'string' }).notNull(),
	validTo: timestamp("valid_to", { withTimezone: true, mode: 'string' }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	roleId: bigint("role_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.roleId],
			foreignColumns: [roles.id],
			name: "role_assignment_history_role_id_807250dc_fk_roles_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "role_assignment_history_user_id_1b78a336_fk_users_id"
		}),
	unique("unique_user_role_start").on(table.validFrom, table.userId, table.roleId),
	check("valid_to_after_valid_from", sql`valid_to >= valid_from`),
]);

export const relationshipType = pgTable("relationship_type", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	relationshipTypeId: bigint("relationship_type_id", { mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "relationship_type_relationship_type_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	relationshipType: varchar("relationship_type", { length: 255 }).notNull(),
}, (table) => [
	unique("relationship_type_relationship_type_key").on(table.relationshipType),
]);

export const tracks = pgTable("tracks", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "tracks_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	trackName: varchar("track_name", { length: 255 }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	stateId: bigint("state_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.stateId],
			foreignColumns: [countryStates.id],
			name: "tracks_state_id_46f6a1ec_fk_country_states_id"
		}),
	unique("tracks_track_name_key").on(table.trackName),
]);

export const studentProfile = pgTable("student_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	pgFirstName: varchar("pg_first_name", { length: 255 }).notNull(),
	pgLastName: varchar("pg_last_name", { length: 255 }).notNull(),
	parentGuardianFlag: boolean("parent_guardian_flag").notNull(),
	schoolName: varchar("school_name", { length: 255 }).notNull(),
	yearLvl: varchar("year_lvl", { length: 255 }).notNull(),
	hasJoinPermission: boolean("has_join_permission").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	interestId: bigint("interest_id", { mode: "number" }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	supervisorId: bigint("supervisor_id", { mode: "number" }),
	joinpermResponseId: varchar("joinperm_responseID", { length: 255 }),
}, (table) => [
	foreignKey({
			columns: [table.interestId],
			foreignColumns: [areasOfInterest.id],
			name: "student_profile_interest_id_fe594703_fk_areas_of_interest_id"
		}),
	foreignKey({
			columns: [table.supervisorId],
			foreignColumns: [supervisorProfile.userId],
			name: "student_profile_supervisor_id_4bc6991c_fk_superviso"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "student_profile_user_id_15556aa0_fk_users_id"
		}),
	check("permission_requires_parent_guardian", sql`(NOT has_join_permission) OR parent_guardian_flag`),
	check("student_first_name_not_empty", sql`NOT ((pg_first_name)::text = ''::text)`),
	check("student_last_name_not_empty", sql`NOT ((pg_last_name)::text = ''::text)`),
	check("student_school_name_not_empty", sql`NOT ((school_name)::text = ''::text)`),
	check("student_year_lvl_valid", sql`(year_lvl)::text = ANY (ARRAY[('9'::character varying)::text, ('10'::character varying)::text, ('11'::character varying)::text, ('12'::character varying)::text])`),
]);

export const supervisorProfile = pgTable("supervisor_profile", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
	schoolName: varchar("school_name", { length: 255 }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "supervisor_profile_user_id_40ae74c6_fk_users_id"
		}),
]);

export const studentSupervisor = pgTable("student_supervisor", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "student_supervisor_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	relationshipTypeId: bigint("relationship_type_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	studentUserId: bigint("student_user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	supervisorUserId: bigint("supervisor_user_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.relationshipTypeId],
			foreignColumns: [relationshipType.relationshipTypeId],
			name: "student_supervisor_relationship_type_id_18e3edd0_fk_relations"
		}),
	foreignKey({
			columns: [table.studentUserId],
			foreignColumns: [studentProfile.userId],
			name: "student_supervisor_student_user_id_fb056317_fk_student_p"
		}),
	foreignKey({
			columns: [table.supervisorUserId],
			foreignColumns: [supervisorProfile.userId],
			name: "student_supervisor_supervisor_user_id_8a5fb4d1_fk_superviso"
		}),
	unique("pk_student_supervisor").on(table.studentUserId, table.supervisorUserId),
	check("no_self_supervision", sql`(supervisor_user_id IS NULL) OR (NOT ((student_user_id = supervisor_user_id) AND (supervisor_user_id IS NOT NULL)))`),
	check("relationship_type_not_null", sql`NOT (relationship_type_id IS NULL)`),
	check("student_user_not_null", sql`NOT (student_user_id IS NULL)`),
]);

export const tasks = pgTable("tasks", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "tasks_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	taskName: varchar("task_name", { length: 255 }).notNull(),
	dueDate: timestamp("due_date", { withTimezone: true, mode: 'string' }).notNull(),
	deletedFlag: boolean("deleted_flag").notNull(),
	taskDescription: varchar("task_description", { length: 255 }),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	milestoneId: bigint("milestone_id", { mode: "number" }),
}, (table) => [
	foreignKey({
			columns: [table.milestoneId],
			foreignColumns: [milestone.id],
			name: "tasks_milestone_id_bdae7b7f_fk_milestone_id"
		}),
]);

export const taskAssignees = pgTable("task_assignees", {
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({ name: "task_assignees_id_seq", startWith: 1, increment: 1, minValue: 1, maxValue: 9223372036854775807, cache: 1 }),
	assignedDatetime: timestamp("assigned_datetime", { withTimezone: true, mode: 'string' }).notNull(),
	deletedFlag: boolean("deleted_flag").notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	userId: bigint("user_id", { mode: "number" }).notNull(),
	// You can use { mode: "bigint" } if numbers are exceeding js number limitations
	taskId: bigint("task_id", { mode: "number" }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.taskId],
			foreignColumns: [tasks.id],
			name: "task_assignees_task_id_dfd06a60_fk_tasks_id"
		}),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "task_assignees_user_id_6b1c6501_fk_users_id"
		}),
	unique("unique_task_user").on(table.userId, table.taskId),
]);
