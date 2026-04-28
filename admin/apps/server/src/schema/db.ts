import {
  pgTable,
  bigint,
  varchar,
  timestamp,
  index,
  unique,
  foreignKey,
  integer,
  check,
  boolean,
  uniqueIndex,
  smallint,
  time,
  text,
  jsonb,
  date,
  numeric,
  interval,
  pgSchema,
  serial,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const djangoMigrations = pgTable("django_migrations", {
  // You can use { mode: "bigint" } if numbers are exceeding js number limitations
  id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
    name: "django_migrations_id_seq",
    startWith: 1,
    increment: 1,
    minValue: 1,
    maxValue: 9223372036854775807,
    cache: 1,
  }),
  app: varchar({ length: 255 }).notNull(),
  name: varchar({ length: 255 }).notNull(),
  applied: timestamp({ withTimezone: true, mode: "string" }).notNull(),
});

export const countries = pgTable(
  "countries",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "countries_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    countryName: varchar("country_name", { length: 255 }).notNull(),
  },
  (table) => [
    index("countries_country_name_3eac3d42_like").using(
      "btree",
      table.countryName.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("countries_country_name_key").on(table.countryName),
  ],
);

export const countryStates = pgTable(
  "country_states",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "country_states_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    stateName: varchar("state_name", { length: 255 }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    countryId: bigint("country_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("country_states_country_id_c84f5fb5").using(
      "btree",
      table.countryId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.countryId],
      foreignColumns: [countries.id],
      name: "country_states_country_id_c84f5fb5_fk_countries_id",
    }),
    unique("unique_state_per_country").on(table.stateName, table.countryId),
  ],
);

export const tracks = pgTable(
  "tracks",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "tracks_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    trackName: varchar("track_name", { length: 100 }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    stateId: bigint("state_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("tracks_state_i_8ee9cb_idx").using(
      "btree",
      table.stateId.asc().nullsLast().op("int8_ops"),
    ),
    index("tracks_state_id_46f6a1ec").using(
      "btree",
      table.stateId.asc().nullsLast().op("int8_ops"),
    ),
    index("tracks_track_name_cf9addea_like").using(
      "btree",
      table.trackName.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    foreignKey({
      columns: [table.stateId],
      foreignColumns: [countryStates.id],
      name: "tracks_state_id_46f6a1ec_fk_country_states_id",
    }),
    unique("tracks_track_name_key").on(table.trackName),
  ],
);

export const djangoContentType = pgTable(
  "django_content_type",
  {
    id: integer().primaryKey().generatedByDefaultAsIdentity({
      name: "django_content_type_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 2147483647,
      cache: 1,
    }),
    appLabel: varchar("app_label", { length: 100 }).notNull(),
    model: varchar({ length: 100 }).notNull(),
  },
  (table) => [
    unique("django_content_type_app_label_model_76bd3d3b_uniq").on(
      table.appLabel,
      table.model,
    ),
  ],
);

export const authPermission = pgTable(
  "auth_permission",
  {
    id: integer().primaryKey().generatedByDefaultAsIdentity({
      name: "auth_permission_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 2147483647,
      cache: 1,
    }),
    name: varchar({ length: 255 }).notNull(),
    contentTypeId: integer("content_type_id").notNull(),
    codename: varchar({ length: 100 }).notNull(),
  },
  (table) => [
    index("auth_permission_content_type_id_2f476e4b").using(
      "btree",
      table.contentTypeId.asc().nullsLast().op("int4_ops"),
    ),
    foreignKey({
      columns: [table.contentTypeId],
      foreignColumns: [djangoContentType.id],
      name: "auth_permission_content_type_id_2f476e4b_fk_django_co",
    }),
    unique("auth_permission_content_type_id_codename_01ab375a_uniq").on(
      table.contentTypeId,
      table.codename,
    ),
  ],
);

export const authGroup = pgTable(
  "auth_group",
  {
    id: integer().primaryKey().generatedByDefaultAsIdentity({
      name: "auth_group_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 2147483647,
      cache: 1,
    }),
    name: varchar({ length: 150 }).notNull(),
  },
  (table) => [
    index("auth_group_name_a6ea08ec_like").using(
      "btree",
      table.name.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("auth_group_name_key").on(table.name),
  ],
);

export const authGroupPermissions = pgTable(
  "auth_group_permissions",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "auth_group_permissions_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    groupId: integer("group_id").notNull(),
    permissionId: integer("permission_id").notNull(),
  },
  (table) => [
    index("auth_group_permissions_group_id_b120cbf9").using(
      "btree",
      table.groupId.asc().nullsLast().op("int4_ops"),
    ),
    index("auth_group_permissions_permission_id_84c5c92e").using(
      "btree",
      table.permissionId.asc().nullsLast().op("int4_ops"),
    ),
    foreignKey({
      columns: [table.permissionId],
      foreignColumns: [authPermission.id],
      name: "auth_group_permissio_permission_id_84c5c92e_fk_auth_perm",
    }),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [authGroup.id],
      name: "auth_group_permissions_group_id_b120cbf9_fk_auth_group_id",
    }),
    unique("auth_group_permissions_group_id_permission_id_0cd325b0_uniq").on(
      table.groupId,
      table.permissionId,
    ),
  ],
);

export const supervisorProfile = pgTable(
  "supervisor_profile",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
    schoolName: varchar("school_name", { length: 255 }).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "supervisor_profile_user_id_40ae74c6_fk_users_id",
    }),
  ],
);

export const studentProfile = pgTable(
  "student_profile",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
    pgFirstName: varchar("pg_first_name", { length: 255 }).notNull(),
    pgLastName: varchar("pg_last_name", { length: 255 }).notNull(),
    pgEmail: varchar("pg_email", { length: 254 }),
    parentGuardianFlag: boolean("parent_guardian_flag").notNull(),
    schoolName: varchar("school_name", { length: 255 }).notNull(),
    yearLvl: varchar("year_lvl", { length: 255 }).notNull(),
    hasJoinPermission: boolean("has_join_permission").notNull(),
    joinpermResponseId: varchar("joinperm_responseID", { length: 255 }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    supervisorId: bigint("supervisor_id", { mode: "number" }),
  },
  (table) => [
    index("student_pro_supervi_0372b3_idx").using(
      "btree",
      table.supervisorId.asc().nullsLast().op("int8_ops"),
    ),
    index("student_profile_supervisor_id_4bc6991c").using(
      "btree",
      table.supervisorId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.supervisorId],
      foreignColumns: [supervisorProfile.userId],
      name: "student_profile_supervisor_id_4bc6991c_fk_superviso",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "student_profile_user_id_15556aa0_fk_users_id",
    }),
    check(
      "permission_requires_parent_guardian",
      sql`(NOT has_join_permission) OR parent_guardian_flag`,
    ),
    check(
      "student_first_name_not_empty",
      sql`NOT ((pg_first_name)::text = ''::text)`,
    ),
    check(
      "student_last_name_not_empty",
      sql`NOT ((pg_last_name)::text = ''::text)`,
    ),
    check(
      "student_school_name_not_empty",
      sql`NOT ((school_name)::text = ''::text)`,
    ),
    check(
      "student_year_lvl_valid",
      sql`(year_lvl)::text = ANY ((ARRAY['9'::character varying, '10'::character varying, '11'::character varying, '12'::character varying])::text[])`,
    ),
  ],
);

export const users = pgTable(
  "users",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "users_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    password: varchar({ length: 128 }).notNull(),
    lastLogin: timestamp("last_login", { withTimezone: true, mode: "string" }),
    isSuperuser: boolean("is_superuser").notNull(),
    isStaff: boolean("is_staff").notNull(),
    dateJoined: timestamp("date_joined", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    email: varchar({ length: 254 }).notNull(),
    firstName: varchar("first_name", { length: 255 }).notNull(),
    lastName: varchar("last_name", { length: 255 }).notNull(),
    isActive: boolean("is_active").notNull(),
    accountStatus: varchar("account_status", { length: 50 }).notNull(),
    invitedAt: timestamp("invited_at", { withTimezone: true, mode: "string" }),
    activatedAt: timestamp("activated_at", {
      withTimezone: true,
      mode: "string",
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
  },
  (table) => [
    index("users_account_33da0c_idx").using(
      "btree",
      table.accountStatus.asc().nullsLast().op("text_ops"),
    ),
    index("users_email_0ea73cca_like").using(
      "btree",
      table.email.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    index("users_track_i_1a6677_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("users_track_id_e7963e8d").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "users_track_id_e7963e8d_fk_tracks_id",
    }),
    unique("users_email_key").on(table.email),
  ],
);

export const usersGroups = pgTable(
  "users_groups",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "users_groups_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    groupId: integer("group_id").notNull(),
  },
  (table) => [
    index("users_groups_group_id_2f3517aa").using(
      "btree",
      table.groupId.asc().nullsLast().op("int4_ops"),
    ),
    index("users_groups_user_id_f500bee5").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [authGroup.id],
      name: "users_groups_group_id_2f3517aa_fk_auth_group_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "users_groups_user_id_f500bee5_fk_users_id",
    }),
    unique("users_groups_user_id_group_id_fc7788e8_uniq").on(
      table.userId,
      table.groupId,
    ),
  ],
);

export const usersUserPermissions = pgTable(
  "users_user_permissions",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "users_user_permissions_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    permissionId: integer("permission_id").notNull(),
  },
  (table) => [
    index("users_user_permissions_permission_id_6d08dcd2").using(
      "btree",
      table.permissionId.asc().nullsLast().op("int4_ops"),
    ),
    index("users_user_permissions_user_id_92473840").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.permissionId],
      foreignColumns: [authPermission.id],
      name: "users_user_permissio_permission_id_6d08dcd2_fk_auth_perm",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "users_user_permissions_user_id_92473840_fk_users_id",
    }),
    unique("users_user_permissions_user_id_permission_id_3b86cbdf_uniq").on(
      table.userId,
      table.permissionId,
    ),
  ],
);

export const adminProfile = pgTable(
  "admin_profile",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    adminId: bigint("admin_id", { mode: "number" }).primaryKey().notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.adminId],
      foreignColumns: [users.id],
      name: "admin_profile_admin_id_d55c5f00_fk_users_id",
    }),
  ],
);

export const adminScope = pgTable(
  "admin_scope",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "admin_scope_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    isGlobal: boolean("is_global").notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("admin_scope_track_i_594c81_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("admin_scope_track_id_633443ef").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("admin_scope_user_id_4ad1f0_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("admin_scope_user_id_c9b7737b").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    uniqueIndex("unique_admin_scope_per_track")
      .using(
        "btree",
        table.userId.asc().nullsLast().op("int8_ops"),
        table.trackId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`(NOT is_global)`),
    uniqueIndex("unique_global_admin_scope")
      .using("btree", table.userId.asc().nullsLast().op("int8_ops"))
      .where(sql`is_global`),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "admin_scope_track_id_633443ef_fk_tracks_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "admin_scope_user_id_c9b7737b_fk_users_id",
    }),
    check(
      "admin_scope_global_or_track",
      sql`(is_global AND (track_id IS NULL)) OR ((NOT is_global) AND (track_id IS NOT NULL))`,
    ),
  ],
);

export const mentorAvailability = pgTable(
  "mentor_availability",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "mentor_availability_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    weekday: smallint().notNull(),
    startTime: time("start_time").notNull(),
    endTime: time("end_time").notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    mentorUserId: bigint("mentor_user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("mentor_avai_mentor__83178e_idx").using(
      "btree",
      table.mentorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("mentor_avai_weekday_25332b_idx").using(
      "btree",
      table.weekday.asc().nullsLast().op("int2_ops"),
    ),
    index("mentor_availability_mentor_user_id_f756a8ac").using(
      "btree",
      table.mentorUserId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.mentorUserId],
      foreignColumns: [users.id],
      name: "mentor_availability_mentor_user_id_f756a8ac_fk_users_id",
    }),
    unique("unique_mentor_availability_slot").on(
      table.weekday,
      table.startTime,
      table.endTime,
      table.mentorUserId,
    ),
    check("mentor_availability_end_after_start", sql`end_time > start_time`),
    check("mentor_availability_weekday_check", sql`weekday >= 0`),
    check(
      "mentor_availability_weekday_valid",
      sql`(weekday >= 0) AND (weekday <= 6)`,
    ),
  ],
);

export const areasOfInterest = pgTable("areas_of_interest", {
  // You can use { mode: "bigint" } if numbers are exceeding js number limitations
  id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
    name: "areas_of_interest_id_seq",
    startWith: 1,
    increment: 1,
    minValue: 1,
    maxValue: 9223372036854775807,
    cache: 1,
  }),
  interestDesc: varchar("interest_desc", { length: 255 }).notNull(),
});

export const userInterest = pgTable(
  "user_interest",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "user_interest_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    interestId: bigint("interest_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("user_intere_interes_4522f5_idx").using(
      "btree",
      table.interestId.asc().nullsLast().op("int8_ops"),
    ),
    index("user_intere_user_id_169ea4_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("user_interest_interest_id_0953fed5").using(
      "btree",
      table.interestId.asc().nullsLast().op("int8_ops"),
    ),
    index("user_interest_user_id_5b53cab9").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.interestId],
      foreignColumns: [areasOfInterest.id],
      name: "user_interest_interest_id_0953fed5_fk_areas_of_interest_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "user_interest_user_id_5b53cab9_fk_users_id",
    }),
    unique("pk_user_interest").on(table.interestId, table.userId),
  ],
);

export const mentorProfile = pgTable(
  "mentor_profile",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).primaryKey().notNull(),
    background: varchar({ length: 50 }),
    institution: varchar("Institution", { length: 255 }).notNull(),
    mentorReason: varchar("mentor_reason", { length: 255 }).notNull(),
    maxGroupCount: integer("max_group_count").notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "mentor_profile_user_id_a4034c13_fk_users_id",
    }),
    check("mentor_max_group_count_non_negative", sql`max_group_count >= 0`),
    check("mentor_profile_max_group_count_check", sql`max_group_count >= 0`),
  ],
);

export const studentSupervisor = pgTable(
  "student_supervisor",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "student_supervisor_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    relationshipType: varchar("relationship_type", { length: 50 }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    studentUserId: bigint("student_user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    supervisorUserId: bigint("supervisor_user_id", { mode: "number" }),
  },
  (table) => [
    index("student_sup_student_0afdc5_idx").using(
      "btree",
      table.studentUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("student_sup_supervi_51462f_idx").using(
      "btree",
      table.supervisorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("student_supervisor_student_user_id_fb056317").using(
      "btree",
      table.studentUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("student_supervisor_supervisor_user_id_8a5fb4d1").using(
      "btree",
      table.supervisorUserId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.studentUserId],
      foreignColumns: [studentProfile.userId],
      name: "student_supervisor_student_user_id_fb056317_fk_student_p",
    }),
    foreignKey({
      columns: [table.supervisorUserId],
      foreignColumns: [supervisorProfile.userId],
      name: "student_supervisor_supervisor_user_id_8a5fb4d1_fk_superviso",
    }),
    unique("pk_student_supervisor").on(
      table.studentUserId,
      table.supervisorUserId,
    ),
    check(
      "no_self_supervision",
      sql`(supervisor_user_id IS NULL) OR (NOT ((student_user_id = supervisor_user_id) AND (supervisor_user_id IS NOT NULL)))`,
    ),
    check("student_user_not_null", sql`NOT (student_user_id IS NULL)`),
  ],
);

export const djangoAdminLog = pgTable(
  "django_admin_log",
  {
    id: integer().primaryKey().generatedByDefaultAsIdentity({
      name: "django_admin_log_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 2147483647,
      cache: 1,
    }),
    actionTime: timestamp("action_time", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    objectId: text("object_id"),
    objectRepr: varchar("object_repr", { length: 200 }).notNull(),
    actionFlag: smallint("action_flag").notNull(),
    changeMessage: text("change_message").notNull(),
    contentTypeId: integer("content_type_id"),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("django_admin_log_content_type_id_c4bce8eb").using(
      "btree",
      table.contentTypeId.asc().nullsLast().op("int4_ops"),
    ),
    index("django_admin_log_user_id_c564eba6").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.contentTypeId],
      foreignColumns: [djangoContentType.id],
      name: "django_admin_log_content_type_id_c4bce8eb_fk_django_co",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "django_admin_log_user_id_c564eba6_fk_users_id",
    }),
    check("django_admin_log_action_flag_check", sql`action_flag >= 0`),
  ],
);

export const resourceTypes = pgTable(
  "resource_types",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "resource_types_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    typeName: varchar("type_name", { length: 50 }).notNull(),
    typeDescription: varchar("type_description", { length: 255 }),
  },
  (table) => [
    index("resource_types_type_name_368352d8_like").using(
      "btree",
      table.typeName.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("resource_types_type_name_key").on(table.typeName),
  ],
);

export const roles = pgTable(
  "roles",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "roles_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    roleName: varchar("role_name", { length: 255 }).notNull(),
  },
  (table) => [
    index("roles_role_name_2c8c2fcd_like").using(
      "btree",
      table.roleName.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("roles_role_name_key").on(table.roleName),
    check("role_name_not_empty", sql`NOT ((role_name)::text = ''::text)`),
  ],
);

export const announcements = pgTable(
  "announcements",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "announcements_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    title: varchar({ length: 255 }).notNull(),
    body: text().notNull(),
    visibilityScope: varchar("visibility_scope", { length: 50 }).notNull(),
    publishedAt: timestamp("published_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    archivedAt: timestamp("archived_at", {
      withTimezone: true,
      mode: "string",
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    authorUserId: bigint("author_user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
  },
  (table) => [
    index("announcemen_archive_36591b_idx").using(
      "btree",
      table.archivedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("announcemen_author__403994_idx").using(
      "btree",
      table.authorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcemen_publish_6b0e06_idx").using(
      "btree",
      table.publishedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("announcemen_track_i_c21806_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcemen_visibil_a80d79_idx").using(
      "btree",
      table.visibilityScope.asc().nullsLast().op("text_ops"),
    ),
    index("announcements_author_user_id_54f6a903").using(
      "btree",
      table.authorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcements_track_id_ba24ce92").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.authorUserId],
      foreignColumns: [users.id],
      name: "announcements_author_user_id_54f6a903_fk_users_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "announcements_track_id_ba24ce92_fk_tracks_id",
    }),
    check(
      "announcement_archived_after_published",
      sql`(archived_at >= published_at) OR (archived_at IS NULL)`,
    ),
  ],
);

export const announcementAudience = pgTable(
  "announcement_audience",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "announcement_audience_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    announcementId: bigint("announcement_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    roleId: bigint("role_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
  },
  (table) => [
    index("announcemen_announc_d9cb5b_idx").using(
      "btree",
      table.announcementId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcemen_role_id_1076c4_idx").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcemen_track_i_391dbc_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcement_audience_announcement_id_25bd1712").using(
      "btree",
      table.announcementId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcement_audience_role_id_571d0f03").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("announcement_audience_track_id_5b49af8c").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    uniqueIndex("unique_announcement_role_audience")
      .using(
        "btree",
        table.announcementId.asc().nullsLast().op("int8_ops"),
        table.roleId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((track_id IS NULL) AND (role_id IS NOT NULL))`),
    uniqueIndex("unique_announcement_role_track_audience")
      .using(
        "btree",
        table.announcementId.asc().nullsLast().op("int8_ops"),
        table.roleId.asc().nullsLast().op("int8_ops"),
        table.trackId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((role_id IS NOT NULL) AND (track_id IS NOT NULL))`),
    uniqueIndex("unique_announcement_track_audience")
      .using(
        "btree",
        table.announcementId.asc().nullsLast().op("int8_ops"),
        table.trackId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((role_id IS NULL) AND (track_id IS NOT NULL))`),
    foreignKey({
      columns: [table.announcementId],
      foreignColumns: [announcements.id],
      name: "announcement_audienc_announcement_id_25bd1712_fk_announcem",
    }),
    foreignKey({
      columns: [table.roleId],
      foreignColumns: [roles.id],
      name: "announcement_audience_role_id_571d0f03_fk_roles_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "announcement_audience_track_id_5b49af8c_fk_tracks_id",
    }),
    check(
      "announcement_audience_requires_role_or_track",
      sql`(role_id IS NOT NULL) OR (track_id IS NOT NULL)`,
    ),
  ],
);

export const auditLog = pgTable(
  "audit_log",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "audit_log_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    entityType: varchar("entity_type", { length: 100 }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    entityId: bigint("entity_id", { mode: "number" }).notNull(),
    action: varchar({ length: 100 }).notNull(),
    beforeState: jsonb("before_state"),
    afterState: jsonb("after_state"),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    actorUserId: bigint("actor_user_id", { mode: "number" }),
  },
  (table) => [
    index("audit_log_action_b32d4d_idx").using(
      "btree",
      table.action.asc().nullsLast().op("text_ops"),
    ),
    index("audit_log_actor_u_ae2850_idx").using(
      "btree",
      table.actorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("audit_log_actor_user_id_147aa761").using(
      "btree",
      table.actorUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("audit_log_created_5a7975_idx").using(
      "btree",
      table.createdAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("audit_log_entity__c2633a_idx").using(
      "btree",
      table.entityType.asc().nullsLast().op("text_ops"),
      table.entityId.asc().nullsLast().op("text_ops"),
    ),
    foreignKey({
      columns: [table.actorUserId],
      foreignColumns: [users.id],
      name: "audit_log_actor_user_id_147aa761_fk_users_id",
    }),
  ],
);

export const certificateType = pgTable(
  "certificate_type",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "certificate_type_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    certificateType: varchar("certificate_type", { length: 255 }).notNull(),
    requiresNumber: boolean("requires_number").notNull(),
    requiresExpiry: boolean("requires_expiry").notNull(),
  },
  (table) => [
    index("certificate_certifi_187256_idx").using(
      "btree",
      table.certificateType.asc().nullsLast().op("text_ops"),
    ),
    index("certificate_type_certificate_type_dc054d41_like").using(
      "btree",
      table.certificateType.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("certificate_type_certificate_type_key").on(table.certificateType),
  ],
);

export const mentorCertificate = pgTable(
  "mentor_certificate",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "mentor_certificate_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    certificateNumber: varchar("certificate_number", { length: 255 }),
    issuedBy: varchar("issued_by", { length: 255 }).notNull(),
    issuedAt: date("issued_at").notNull(),
    expiresAt: date("expires_at"),
    fileUrl: varchar("file_url", { length: 500 }),
    verified: boolean().notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    certificateTypeId: bigint("certificate_type_id", {
      mode: "number",
    }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    mentorProfileId: bigint("mentor_profile_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("mentor_cert_mentor__f7358b_idx").using(
      "btree",
      table.mentorProfileId.asc().nullsLast().op("int8_ops"),
      table.certificateTypeId.asc().nullsLast().op("int8_ops"),
    ),
    index("mentor_certificate_certificate_type_id_090af26f").using(
      "btree",
      table.certificateTypeId.asc().nullsLast().op("int8_ops"),
    ),
    index("mentor_certificate_mentor_profile_id_61bbc118").using(
      "btree",
      table.mentorProfileId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.certificateTypeId],
      foreignColumns: [certificateType.id],
      name: "mentor_certificate_certificate_type_id_090af26f_fk_certifica",
    }),
    foreignKey({
      columns: [table.mentorProfileId],
      foreignColumns: [mentorProfile.userId],
      name: "mentor_certificate_mentor_profile_id_61bbc118_fk_mentor_pr",
    }),
    unique("unique_certificate_per_mentor").on(
      table.certificateNumber,
      table.certificateTypeId,
      table.mentorProfileId,
    ),
    check(
      "cannot_verify_expired_certificate",
      sql`(expires_at IS NULL) OR (expires_at >= statement_timestamp()) OR (NOT verified)`,
    ),
  ],
);

export const messageResources = pgTable(
  "message_resources",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "message_resources_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    resourceId: bigint("resource_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    messageId: bigint("message_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("message_res_message_8048ce_idx").using(
      "btree",
      table.messageId.asc().nullsLast().op("int8_ops"),
    ),
    index("message_res_resourc_d3776f_idx").using(
      "btree",
      table.resourceId.asc().nullsLast().op("int8_ops"),
    ),
    index("message_resources_message_id_e0b74b54").using(
      "btree",
      table.messageId.asc().nullsLast().op("int8_ops"),
    ),
    index("message_resources_resource_id_7bf8fbc9").using(
      "btree",
      table.resourceId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.messageId],
      foreignColumns: [messages.id],
      name: "message_resources_message_id_e0b74b54_fk_messages_id",
    }),
    foreignKey({
      columns: [table.resourceId],
      foreignColumns: [resources.id],
      name: "message_resources_resource_id_7bf8fbc9_fk_resources_id",
    }),
    unique("message_resources_message_id_resource_id_9a04fab7_uniq").on(
      table.resourceId,
      table.messageId,
    ),
  ],
);

export const messageStatus = pgTable(
  "message_status",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "message_status_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    status: varchar({ length: 20 }).notNull(),
    deliveredAt: timestamp("delivered_at", {
      withTimezone: true,
      mode: "string",
    }),
    readAt: timestamp("read_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    messageId: bigint("message_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("message_sta_message_5f9800_idx").using(
      "btree",
      table.messageId.asc().nullsLast().op("int8_ops"),
    ),
    index("message_sta_user_id_2503ad_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
      table.status.asc().nullsLast().op("text_ops"),
    ),
    index("message_status_message_id_7d8e74e7").using(
      "btree",
      table.messageId.asc().nullsLast().op("int8_ops"),
    ),
    index("message_status_user_id_0673798e").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.messageId],
      foreignColumns: [messages.id],
      name: "message_status_message_id_7d8e74e7_fk_messages_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "message_status_user_id_0673798e_fk_users_id",
    }),
    unique("message_status_message_id_user_id_e0eb32f9_uniq").on(
      table.messageId,
      table.userId,
    ),
  ],
);

export const messages = pgTable(
  "messages",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "messages_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    messageText: text("message_text").notNull(),
    sentAt: timestamp("sent_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    editedAt: timestamp("edited_at", { withTimezone: true, mode: "string" }),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    messageType: varchar("message_type", { length: 20 }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    senderUserId: bigint("sender_user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("messages_deleted_555c2c_idx").using(
      "btree",
      table.deletedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("messages_group_i_18591d_idx").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
      table.sentAt.asc().nullsLast().op("int8_ops"),
    ),
    index("messages_group_id_0fd96228").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("messages_sender__199d51_idx").using(
      "btree",
      table.senderUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("messages_sender_user_id_b1b10099").using(
      "btree",
      table.senderUserId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "messages_group_id_0fd96228_fk_groups_id",
    }),
    foreignKey({
      columns: [table.senderUserId],
      foreignColumns: [users.id],
      name: "messages_sender_user_id_b1b10099_fk_users_id",
    }),
    check(
      "message_deleted_after_sent",
      sql`(deleted_at IS NULL) OR (deleted_at >= sent_at)`,
    ),
    check(
      "message_edited_after_sent",
      sql`(edited_at IS NULL) OR (edited_at >= sent_at)`,
    ),
  ],
);

export const events = pgTable(
  "events",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "events_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    eventName: varchar("event_name", { length: 255 }).notNull(),
    description: text(),
    eventType: varchar("event_type", { length: 100 }),
    startDatetime: timestamp("start_datetime", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    endsDatetime: timestamp("ends_datetime", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    location: varchar({ length: 255 }),
    humanitixLink: varchar("humanitix_link", { length: 255 }),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    eventImage: varchar("event_image", { length: 255 }),
    isVirtual: boolean("is_virtual").notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    hostUserId: bigint("host_user_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
  },
  (table) => [
    index("events_host_us_34c951_idx").using(
      "btree",
      table.hostUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("events_host_user_id_f7fc239c").using(
      "btree",
      table.hostUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("events_start_d_2ddaa0_idx").using(
      "btree",
      table.startDatetime.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("events_track_i_d7b306_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("events_track_id_a0bf15c2").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.hostUserId],
      foreignColumns: [users.id],
      name: "events_host_user_id_f7fc239c_fk_users_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "events_track_id_a0bf15c2_fk_tracks_id",
    }),
    check("check_event_end_after_start", sql`ends_datetime > start_datetime`),
    check(
      "check_virtual_location_null",
      sql`(NOT is_virtual) OR (location IS NULL)`,
    ),
  ],
);

export const eventTargetGroup = pgTable(
  "event_target_group",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "event_target_group_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    eventId: bigint("event_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("event_targe_event_i_d53a84_idx").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_targe_group_i_29198c_idx").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_group_event_id_3102faf9").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_group_group_id_9b0af69c").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.eventId],
      foreignColumns: [events.id],
      name: "event_target_group_event_id_3102faf9_fk_events_id",
    }),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "event_target_group_group_id_9b0af69c_fk_groups_id",
    }),
    unique("unique_event_group").on(table.eventId, table.groupId),
  ],
);

export const eventTargetRole = pgTable(
  "event_target_role",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "event_target_role_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    eventId: bigint("event_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    roleId: bigint("role_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("event_targe_event_i_bcd600_idx").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_targe_role_id_6f7b73_idx").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_role_event_id_62145d19").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_role_role_id_f7baea72").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.eventId],
      foreignColumns: [events.id],
      name: "event_target_role_event_id_62145d19_fk_events_id",
    }),
    foreignKey({
      columns: [table.roleId],
      foreignColumns: [roles.id],
      name: "event_target_role_role_id_f7baea72_fk_roles_id",
    }),
    unique("unique_event_role").on(table.eventId, table.roleId),
  ],
);

export const eventTargetTrack = pgTable(
  "event_target_track",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "event_target_track_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    eventId: bigint("event_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("event_targe_event_i_2f7445_idx").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_targe_track_i_96c57e_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_track_event_id_d4858886").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_target_track_track_id_1163cca1").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.eventId],
      foreignColumns: [events.id],
      name: "event_target_track_event_id_d4858886_fk_events_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "event_target_track_track_id_1163cca1_fk_tracks_id",
    }),
    unique("unique_event_track").on(table.eventId, table.trackId),
  ],
);

export const eventRsvp = pgTable(
  "event_rsvp",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "event_rsvp_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    rsvpStatus: varchar("rsvp_status", { length: 50 }).notNull(),
    respondedAt: timestamp("responded_at", {
      withTimezone: true,
      mode: "string",
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    eventId: bigint("event_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("event_rsvp_event_i_393d63_idx").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_rsvp_event_id_8ccc26b8").using(
      "btree",
      table.eventId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_rsvp_rsvp_st_80e8a8_idx").using(
      "btree",
      table.rsvpStatus.asc().nullsLast().op("text_ops"),
    ),
    index("event_rsvp_user_id_59b81e_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("event_rsvp_user_id_c3df2ffd").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.eventId],
      foreignColumns: [events.id],
      name: "event_rsvp_event_id_8ccc26b8_fk_events_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "event_rsvp_user_id_c3df2ffd_fk_users_id",
    }),
    unique("unique_event_rsvp_user").on(table.userId, table.eventId),
    check(
      "event_rsvp_response_state_valid",
      sql`(responded_at IS NULL) OR ((rsvp_status)::text = ANY ((ARRAY['going'::character varying, 'maybe'::character varying, 'declined'::character varying])::text[]))`,
    ),
  ],
);

export const groupMembership = pgTable(
  "group_membership",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "group_membership_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    membershipRole: varchar("membership_role", { length: 50 }).notNull(),
    joinedAt: timestamp("joined_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    leftAt: timestamp("left_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("group_membe_group_i_e52645_idx").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("group_membe_left_at_e9e6a8_idx").using(
      "btree",
      table.leftAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("group_membe_user_id_9eabd2_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("group_membership_group_id_45c6964f").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("group_membership_user_id_35a27eaa").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    uniqueIndex("unique_active_group_membership")
      .using(
        "btree",
        table.groupId.asc().nullsLast().op("int8_ops"),
        table.userId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`(left_at IS NULL)`),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "group_membership_group_id_45c6964f_fk_groups_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "group_membership_user_id_35a27eaa_fk_users_id",
    }),
    check(
      "group_membership_left_after_joined",
      sql`(left_at >= joined_at) OR (left_at IS NULL)`,
    ),
  ],
);

export const groups = pgTable(
  "groups",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "groups_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    groupName: varchar("group_name", { length: 255 }).notNull(),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("groups_created_d34ebd_idx").using(
      "btree",
      table.createdAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("groups_deleted_8ee2fc_idx").using(
      "btree",
      table.deletedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("groups_track_i_093220_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("groups_track_id_f29fde9a").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    uniqueIndex("unique_active_group_name_per_track")
      .using(
        "btree",
        table.trackId.asc().nullsLast().op("text_ops"),
        table.groupName.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`(deleted_at IS NULL)`),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "groups_track_id_f29fde9a_fk_tracks_id",
    }),
    check(
      "group_deleted_after_created",
      sql`(deleted_at >= created_at) OR (deleted_at IS NULL)`,
    ),
    check(
      "group_name_not_empty",
      sql`NOT ((group_name)::text ~ '^\s*$'::text)`,
    ),
  ],
);

export const matchingMentor = pgTable(
  "matching_mentor",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_mentor_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    firstName: varchar("first_name", { length: 80 }).notNull(),
    lastName: varchar("last_name", { length: 80 }).notNull(),
    email: varchar({ length: 254 }).notNull(),
    isActive: boolean("is_active").notNull(),
    background: varchar({ length: 120 }).notNull(),
    institution: varchar({ length: 200 }).notNull(),
    country: varchar({ length: 80 }).notNull(),
    region: varchar({ length: 80 }).notNull(),
    track: varchar({ length: 16 }).notNull(),
    maxGroups: smallint("max_groups").notNull(),
  },
  (table) => [
    index("matching_mentor_email_a48af002_like").using(
      "btree",
      table.email.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("matching_mentor_email_key").on(table.email),
    check("matching_mentor_max_groups_check", sql`max_groups >= 0`),
  ],
);

export const matchingMentorInterests = pgTable(
  "matching_mentor_interests",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_mentor_interests_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    mentorId: bigint("mentor_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    interestId: bigint("interest_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("matching_mentor_interests_interest_id_9292dd16").using(
      "btree",
      table.interestId.asc().nullsLast().op("int8_ops"),
    ),
    index("matching_mentor_interests_mentor_id_d5e11250").using(
      "btree",
      table.mentorId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.interestId],
      foreignColumns: [matchingInterest.id],
      name: "matching_mentor_inte_interest_id_9292dd16_fk_matching_",
    }),
    foreignKey({
      columns: [table.mentorId],
      foreignColumns: [matchingMentor.id],
      name: "matching_mentor_inte_mentor_id_d5e11250_fk_matching_",
    }),
    unique("matching_mentor_interests_mentor_id_interest_id_ad1fe674_uniq").on(
      table.mentorId,
      table.interestId,
    ),
  ],
);

export const matchingInterest = pgTable(
  "matching_interest",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_interest_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    name: varchar({ length: 80 }).notNull(),
  },
  (table) => [
    index("matching_interest_name_860b2179_like").using(
      "btree",
      table.name.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("matching_interest_name_key").on(table.name),
  ],
);

export const matchingStudent = pgTable(
  "matching_student",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_student_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    firstName: varchar("first_name", { length: 80 }).notNull(),
    lastName: varchar("last_name", { length: 80 }).notNull(),
    email: varchar({ length: 254 }).notNull(),
    supervisorEmail: varchar("supervisor_email", { length: 254 }).notNull(),
    school: varchar({ length: 200 }).notNull(),
    yearLevel: smallint("year_level").notNull(),
    country: varchar({ length: 80 }).notNull(),
    region: varchar({ length: 80 }).notNull(),
    preassignedGroup: varchar("preassigned_group", { length: 64 }).notNull(),
    track: varchar({ length: 16 }).notNull(),
  },
  (table) => [
    index("matching_student_email_aa9b61cf_like").using(
      "btree",
      table.email.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    unique("matching_student_email_key").on(table.email),
    check("matching_student_year_level_check", sql`year_level >= 0`),
  ],
);

export const matchingStudentInterests = pgTable(
  "matching_student_interests",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_student_interests_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    studentId: bigint("student_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    interestId: bigint("interest_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("matching_student_interests_interest_id_b50a0b8a").using(
      "btree",
      table.interestId.asc().nullsLast().op("int8_ops"),
    ),
    index("matching_student_interests_student_id_0d287558").using(
      "btree",
      table.studentId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.interestId],
      foreignColumns: [matchingInterest.id],
      name: "matching_student_int_interest_id_b50a0b8a_fk_matching_",
    }),
    foreignKey({
      columns: [table.studentId],
      foreignColumns: [matchingStudent.id],
      name: "matching_student_int_student_id_0d287558_fk_matching_",
    }),
    unique(
      "matching_student_interests_student_id_interest_id_df98b935_uniq",
    ).on(table.studentId, table.interestId),
  ],
);

export const matchingStudentgroup = pgTable(
  "matching_studentgroup",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_studentgroup_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    name: varchar({ length: 120 }).notNull(),
    track: varchar({ length: 16 }).notNull(),
    yearMin: smallint("year_min"),
    yearMax: smallint("year_max"),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    mentorId: bigint("mentor_id", { mode: "number" }),
  },
  (table) => [
    index("matching_studentgroup_mentor_id_318e9d58").using(
      "btree",
      table.mentorId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.mentorId],
      foreignColumns: [matchingMentor.id],
      name: "matching_studentgroup_mentor_id_318e9d58_fk_matching_mentor_id",
    }),
    check("matching_studentgroup_year_max_check", sql`year_max >= 0`),
    check("matching_studentgroup_year_min_check", sql`year_min >= 0`),
  ],
);

export const matchingStudentgroupInterests = pgTable(
  "matching_studentgroup_interests",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_studentgroup_interests_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    studentgroupId: bigint("studentgroup_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    interestId: bigint("interest_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("matching_studentgroup_interests_interest_id_39fc584d").using(
      "btree",
      table.interestId.asc().nullsLast().op("int8_ops"),
    ),
    index("matching_studentgroup_interests_studentgroup_id_de9a8747").using(
      "btree",
      table.studentgroupId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.interestId],
      foreignColumns: [matchingInterest.id],
      name: "matching_studentgrou_interest_id_39fc584d_fk_matching_",
    }),
    foreignKey({
      columns: [table.studentgroupId],
      foreignColumns: [matchingStudentgroup.id],
      name: "matching_studentgrou_studentgroup_id_de9a8747_fk_matching_",
    }),
    unique(
      "matching_studentgroup_in_studentgroup_id_interest_79199744_uniq",
    ).on(table.studentgroupId, table.interestId),
  ],
);

export const matchingStudentgroupMembers = pgTable(
  "matching_studentgroup_members",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_studentgroup_members_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    studentgroupId: bigint("studentgroup_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    studentId: bigint("student_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("matching_studentgroup_members_student_id_f22f0640").using(
      "btree",
      table.studentId.asc().nullsLast().op("int8_ops"),
    ),
    index("matching_studentgroup_members_studentgroup_id_010376c8").using(
      "btree",
      table.studentgroupId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.studentId],
      foreignColumns: [matchingStudent.id],
      name: "matching_studentgrou_student_id_f22f0640_fk_matching_",
    }),
    foreignKey({
      columns: [table.studentgroupId],
      foreignColumns: [matchingStudentgroup.id],
      name: "matching_studentgrou_studentgroup_id_010376c8_fk_matching_",
    }),
    unique(
      "matching_studentgroup_me_studentgroup_id_student__3bdd378f_uniq",
    ).on(table.studentgroupId, table.studentId),
  ],
);

export const matchingMentoravailability = pgTable(
  "matching_mentoravailability",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "matching_mentoravailability_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    weekday: smallint().notNull(),
    start: time().notNull(),
    end: time().notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    mentorId: bigint("mentor_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("matching_mentoravailability_mentor_id_468a5bf9").using(
      "btree",
      table.mentorId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.mentorId],
      foreignColumns: [matchingMentor.id],
      name: "matching_mentoravail_mentor_id_468a5bf9_fk_matching_",
    }),
    unique(
      "matching_mentoravailabil_mentor_id_weekday_start__9e83be24_uniq",
    ).on(table.weekday, table.start, table.end, table.mentorId),
    check("matching_mentoravailability_weekday_check", sql`weekday >= 0`),
  ],
);

export const roleAssignmentHistory = pgTable(
  "role_assignment_history",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "role_assignment_history_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    validFrom: timestamp("valid_from", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    validTo: timestamp("valid_to", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    roleId: bigint("role_id", { mode: "number" }),
  },
  (table) => [
    index("role_assign_role_id_e11f96_idx").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("role_assign_user_id_4edae0_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("role_assignment_history_role_id_807250dc").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("role_assignment_history_user_id_1b78a336").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.roleId],
      foreignColumns: [roles.id],
      name: "role_assignment_history_role_id_807250dc_fk_roles_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "role_assignment_history_user_id_1b78a336_fk_users_id",
    }),
    unique("unique_user_role_start").on(
      table.validFrom,
      table.userId,
      table.roleId,
    ),
    check("valid_to_after_valid_from", sql`valid_to >= valid_from`),
  ],
);

export const resourceAudience = pgTable(
  "resource_audience",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "resource_audience_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    resourceId: bigint("resource_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    roleId: bigint("role_id", { mode: "number" }),
  },
  (table) => [
    index("resource_au_resourc_cef2c2_idx").using(
      "btree",
      table.resourceId.asc().nullsLast().op("int8_ops"),
    ),
    index("resource_au_role_id_9287b0_idx").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("resource_au_track_i_8569c2_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("resource_audience_resource_id_4a807083").using(
      "btree",
      table.resourceId.asc().nullsLast().op("int8_ops"),
    ),
    index("resource_audience_role_id_34580b4e").using(
      "btree",
      table.roleId.asc().nullsLast().op("int8_ops"),
    ),
    index("resource_audience_track_id_8c2cfbea").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    uniqueIndex("unique_resource_role_audience")
      .using(
        "btree",
        table.resourceId.asc().nullsLast().op("int8_ops"),
        table.roleId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((track_id IS NULL) AND (role_id IS NOT NULL))`),
    uniqueIndex("unique_resource_role_track_audience")
      .using(
        "btree",
        table.resourceId.asc().nullsLast().op("int8_ops"),
        table.roleId.asc().nullsLast().op("int8_ops"),
        table.trackId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((role_id IS NOT NULL) AND (track_id IS NOT NULL))`),
    uniqueIndex("unique_resource_track_audience")
      .using(
        "btree",
        table.resourceId.asc().nullsLast().op("int8_ops"),
        table.trackId.asc().nullsLast().op("int8_ops"),
      )
      .where(sql`((role_id IS NULL) AND (track_id IS NOT NULL))`),
    foreignKey({
      columns: [table.resourceId],
      foreignColumns: [resources.id],
      name: "resource_audience_resource_id_4a807083_fk_resources_id",
    }),
    foreignKey({
      columns: [table.roleId],
      foreignColumns: [roles.id],
      name: "resource_audience_role_id_34580b4e_fk_roles_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "resource_audience_track_id_8c2cfbea_fk_tracks_id",
    }),
    check(
      "resource_audience_requires_role_or_track",
      sql`(role_id IS NOT NULL) OR (track_id IS NOT NULL)`,
    ),
  ],
);

export const loginTokens = pgTable(
  "login_tokens",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "login_tokens_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    token: varchar({ length: 6 }).notNull(),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    expiresAt: timestamp("expires_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    used: boolean().notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("login_token_created_7a566c_idx").using(
      "btree",
      table.createdAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("login_token_expires_133cb3_idx").using(
      "btree",
      table.expiresAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("login_token_user_id_e66ea4_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
      table.token.asc().nullsLast().op("int8_ops"),
    ),
    index("login_tokens_user_id_7f12777f").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "login_tokens_user_id_7f12777f_fk_users_id",
    }),
  ],
);

export const djangoSession = pgTable(
  "django_session",
  {
    sessionKey: varchar("session_key", { length: 40 }).primaryKey().notNull(),
    sessionData: text("session_data").notNull(),
    expireDate: timestamp("expire_date", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
  },
  (table) => [
    index("django_session_expire_date_a5c62663").using(
      "btree",
      table.expireDate.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("django_session_session_key_c0390e0f_like").using(
      "btree",
      table.sessionKey.asc().nullsLast().op("varchar_pattern_ops"),
    ),
  ],
);

export const milestone = pgTable(
  "milestone",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "milestone_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    milestoneName: varchar("milestone_name", { length: 255 }).notNull(),
    completed: boolean().notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("milestone_complet_c0474d_idx").using(
      "btree",
      table.completed.asc().nullsLast().op("bool_ops"),
    ),
    index("milestone_deleted_737b8a_idx").using(
      "btree",
      table.deletedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("milestone_group_i_aa2495_idx").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("milestone_group_id_11a6a79d").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "milestone_group_id_11a6a79d_fk_groups_id",
    }),
  ],
);

export const tasks = pgTable(
  "tasks",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "tasks_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    taskName: varchar("task_name", { length: 255 }).notNull(),
    dueDate: timestamp("due_date", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    taskDescription: varchar("task_description", { length: 255 }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    milestoneId: bigint("milestone_id", { mode: "number" }),
  },
  (table) => [
    index("tasks_deleted_1d9a30_idx").using(
      "btree",
      table.deletedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("tasks_due_dat_0359a9_idx").using(
      "btree",
      table.dueDate.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("tasks_milesto_5735eb_idx").using(
      "btree",
      table.milestoneId.asc().nullsLast().op("int8_ops"),
    ),
    index("tasks_milestone_id_bdae7b7f").using(
      "btree",
      table.milestoneId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.milestoneId],
      foreignColumns: [milestone.id],
      name: "tasks_milestone_id_bdae7b7f_fk_milestone_id",
    }),
  ],
);

export const taskAssignees = pgTable(
  "task_assignees",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "task_assignees_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    assignedDatetime: timestamp("assigned_datetime", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    taskId: bigint("task_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("ta_active_by_task")
      .using("btree", table.taskId.asc().nullsLast().op("int8_ops"))
      .where(sql`(deleted_at IS NULL)`),
    index("ta_active_by_user")
      .using("btree", table.userId.asc().nullsLast().op("int8_ops"))
      .where(sql`(deleted_at IS NULL)`),
    index("task_assign_assigne_94a93f_idx").using(
      "btree",
      table.assignedDatetime.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("task_assign_task_id_39473c_idx").using(
      "btree",
      table.taskId.asc().nullsLast().op("int8_ops"),
    ),
    index("task_assign_user_id_504562_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("task_assignees_task_id_dfd06a60").using(
      "btree",
      table.taskId.asc().nullsLast().op("int8_ops"),
    ),
    index("task_assignees_user_id_6b1c6501").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.taskId],
      foreignColumns: [tasks.id],
      name: "task_assignees_task_id_dfd06a60_fk_tasks_id",
    }),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "task_assignees_user_id_6b1c6501_fk_users_id",
    }),
    unique("unique_task_user").on(table.userId, table.taskId),
  ],
);

export const userSession = pgTable(
  "user_session",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "user_session_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    sid: varchar({ length: 64 }).notNull(),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    lastActivityAt: timestamp("last_activity_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    expiresAt: timestamp("expires_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    endedAt: timestamp("ended_at", { withTimezone: true, mode: "string" }),
    revokedAt: timestamp("revoked_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("user_sessio_expires_85bda6_idx").using(
      "btree",
      table.expiresAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("user_sessio_last_ac_a7b43b_idx").using(
      "btree",
      table.lastActivityAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("user_sessio_sid_1a73c0_idx").using(
      "btree",
      table.sid.asc().nullsLast().op("text_ops"),
    ),
    index("user_sessio_user_id_c6fc39_idx").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("user_session_sid_17ee7496_like").using(
      "btree",
      table.sid.asc().nullsLast().op("varchar_pattern_ops"),
    ),
    index("user_session_user_id_babcef0a").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "user_session_user_id_babcef0a_fk_users_id",
    }),
    unique("user_session_sid_key").on(table.sid),
    check(
      "user_session_activity_after_created",
      sql`last_activity_at >= created_at`,
    ),
    check(
      "user_session_ended_after_created",
      sql`(ended_at >= created_at) OR (ended_at IS NULL)`,
    ),
    check("user_session_expires_after_created", sql`expires_at >= created_at`),
    check(
      "user_session_revoked_after_created",
      sql`(revoked_at >= created_at) OR (revoked_at IS NULL)`,
    ),
  ],
);

export const alert = pgTable(
  "alert",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "alert_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    errorReason: varchar("error_reason", { length: 255 }).notNull(),
    resolved: boolean().notNull(),
    resolvedAt: timestamp("resolved_at", {
      withTimezone: true,
      mode: "string",
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    sessionId: bigint("session_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("alert_created_417cb1_idx").using(
      "btree",
      table.createdAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("alert_resolve_79070e_idx").using(
      "btree",
      table.resolved.asc().nullsLast().op("bool_ops"),
    ),
    index("alert_session_0863a0_idx").using(
      "btree",
      table.sessionId.asc().nullsLast().op("int8_ops"),
    ),
    index("alert_session_id_5bdcb2f5").using(
      "btree",
      table.sessionId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.sessionId],
      foreignColumns: [userSession.id],
      name: "alert_session_id_5bdcb2f5_fk_user_session_id",
    }),
    check("alert_reason_not_empty", sql`NOT ((error_reason)::text = ''::text)`),
    check(
      "alert_resolved_after_created",
      sql`(resolved_at >= created_at) OR (resolved_at IS NULL)`,
    ),
    check(
      "alert_resolved_matches_timestamp",
      sql`((NOT resolved) AND (resolved_at IS NULL)) OR (resolved AND (resolved_at IS NOT NULL))`,
    ),
  ],
);

export const workshops = pgTable(
  "workshops",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    workshopId: bigint("workshop_id", { mode: "number" })
      .primaryKey()
      .generatedByDefaultAsIdentity({
        name: "workshops_workshop_id_seq",
        startWith: 1,
        increment: 1,
        minValue: 1,
        maxValue: 9223372036854775807,
        cache: 1,
      }),
    workshopName: varchar("workshop_name", { length: 255 }).notNull(),
    startDatetime: timestamp("start_datetime", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    duration: interval().notNull(),
    location: varchar({ length: 255 }).notNull(),
    description: varchar({ length: 255 }),
    zoomLink: varchar("zoom_link", { length: 255 }),
    deletedFlag: boolean("deleted_flag").notNull(),
    deletedDatetime: timestamp("deleted_datetime", {
      withTimezone: true,
      mode: "string",
    }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    hostUserId: bigint("host_user_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("workshops_group_i_f53249_idx").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("workshops_group_id_452b7f33").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("workshops_host_us_e187e4_idx").using(
      "btree",
      table.hostUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("workshops_host_user_id_c0c274b0").using(
      "btree",
      table.hostUserId.asc().nullsLast().op("int8_ops"),
    ),
    index("workshops_start_d_ee3d73_idx").using(
      "btree",
      table.startDatetime.asc().nullsLast().op("timestamptz_ops"),
    ),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "workshops_group_id_452b7f33_fk_groups_id",
    }),
    foreignKey({
      columns: [table.hostUserId],
      foreignColumns: [users.id],
      name: "workshops_host_user_id_c0c274b0_fk_users_id",
    }),
  ],
);

export const workshopAttendance = pgTable(
  "workshop_attendance",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "workshop_attendance_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    responded: boolean().notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    userId: bigint("user_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    workshopId: bigint("workshop_id", { mode: "number" }).notNull(),
  },
  (table) => [
    index("workshop_attendance_user_id_c7587c90").using(
      "btree",
      table.userId.asc().nullsLast().op("int8_ops"),
    ),
    index("workshop_attendance_workshop_id_15b47095").using(
      "btree",
      table.workshopId.asc().nullsLast().op("int8_ops"),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: "workshop_attendance_user_id_c7587c90_fk_users_id",
    }),
    foreignKey({
      columns: [table.workshopId],
      foreignColumns: [workshops.workshopId],
      name: "workshop_attendance_workshop_id_15b47095_fk_workshops",
    }),
    unique("pk_workshop_attendance").on(table.userId, table.workshopId),
  ],
);

export const resources = pgTable(
  "resources",
  {
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    id: bigint({ mode: "number" }).primaryKey().generatedByDefaultAsIdentity({
      name: "resources_id_seq",
      startWith: 1,
      increment: 1,
      minValue: 1,
      maxValue: 9223372036854775807,
      cache: 1,
    }),
    name: varchar({ length: 255 }).notNull(),
    description: varchar({ length: 255 }).notNull(),
    visibilityScope: varchar("visibility_scope", { length: 50 }).notNull(),
    uploadedAt: timestamp("uploaded_at", {
      withTimezone: true,
      mode: "string",
    }).notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    trackId: bigint("track_id", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    uploadedById: bigint("uploaded_by_id", { mode: "number" }).notNull(),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    typeId: bigint("type_id", { mode: "number" }),
    fileMimeType: varchar("file_mime_type", { length: 100 }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    fileSize: bigint("file_size", { mode: "number" }),
    // You can use { mode: "bigint" } if numbers are exceeding js number limitations
    groupId: bigint("group_id", { mode: "number" }),
    kind: varchar({ length: 50 }).notNull(),
    storageKey: varchar("storage_key", { length: 255 }),
  },
  (table) => [
    index("resources_deleted_77ce14_idx").using(
      "btree",
      table.deletedAt.asc().nullsLast().op("timestamptz_ops"),
    ),
    index("resources_group_id_5680e4d8").using(
      "btree",
      table.groupId.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_resource_type_id_8ca31a8a").using(
      "btree",
      table.typeId.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_track_i_c53699_idx").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_track_id_c4079c5a").using(
      "btree",
      table.trackId.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_uploade_d26da4_idx").using(
      "btree",
      table.uploadedById.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_uploader_user_id_id_f9418bc1").using(
      "btree",
      table.uploadedById.asc().nullsLast().op("int8_ops"),
    ),
    index("resources_visibil_2b2301_idx").using(
      "btree",
      table.visibilityScope.asc().nullsLast().op("text_ops"),
    ),
    foreignKey({
      columns: [table.groupId],
      foreignColumns: [groups.id],
      name: "resources_group_id_5680e4d8_fk_groups_id",
    }),
    foreignKey({
      columns: [table.trackId],
      foreignColumns: [tracks.id],
      name: "resources_track_id_c4079c5a_fk_tracks_id",
    }),
    foreignKey({
      columns: [table.typeId],
      foreignColumns: [resourceTypes.id],
      name: "resources_type_id_93682dd6_fk_resource_types_id",
    }),
    foreignKey({
      columns: [table.uploadedById],
      foreignColumns: [users.id],
      name: "resources_uploaded_by_id_918d19f2_fk_users_id",
    }),
    check(
      "deleted_after_upload",
      sql`(deleted_at >= uploaded_at) OR (deleted_at IS NULL)`,
    ),
    check(
      "resource_description_not_empty",
      sql`NOT ((description)::text = ''::text)`,
    ),
  ],
);
