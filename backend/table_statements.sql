CREATE TABLE "users"(
    "user_id" INTEGER NOT NULL,
    "first_name" VARCHAR(255) NOT NULL,
    "last_name" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "status" BOOLEAN NOT NULL,
    "track_id" INTEGER NOT NULL,
    "state_id" INTEGER NOT NULL
);
ALTER TABLE
    "users" ADD PRIMARY KEY("user_id");
CREATE TABLE "mentor_profile"(
    "user_id (FK)" INTEGER NOT NULL,
    "background_id(FK)" INTEGER NOT NULL,
    "Institution" VARCHAR(255) NOT NULL,
    "mentor_reason" VARCHAR(255) NOT NULL,
    "max_grp_cnt" INTEGER NOT NULL
);
ALTER TABLE
    "mentor_profile" ADD PRIMARY KEY("user_id (FK)");
CREATE TABLE "groups"(
    "group_id" INTEGER NOT NULL,
    "group_name" VARCHAR(255) NOT NULL,
    "track_id (FK)" INTEGER NOT NULL,
    "creation_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "deleted_flag" BOOLEAN NOT NULL,
        "deleted_datetime" TIMESTAMP(0)
    WITH
        TIME zone NOT NULL
);
ALTER TABLE
    "groups" ADD PRIMARY KEY("group_id");
CREATE TABLE "student_profile"(
    "user_id (FK)" INTEGER NOT NULL,
    "pg_first_name" VARCHAR(255) NOT NULL,
    "pg_last_name" VARCHAR(255) NOT NULL,
    "parent_guardian_flag" VARCHAR(255) CHECK
        ("parent_guardian_flag" IN('')) NOT NULL,
        "supervisor_id (FK)" INTEGER NOT NULL,
        "interest_id (FK)" INTEGER NOT NULL,
        "school_name" VARCHAR(255) NOT NULL,
        "year_lvl" VARCHAR(255)
    CHECK
        ("year_lvl" IN('')) NOT NULL,
        "has_join_permission" BOOLEAN NOT NULL
);
ALTER TABLE
    "student_profile" ADD PRIMARY KEY("user_id (FK)");
CREATE TABLE "roles"(
    "role_id" INTEGER NOT NULL,
    "role_name" VARCHAR(255) CHECK
        ("role_name" IN('')) NOT NULL
);
ALTER TABLE
    "roles" ADD PRIMARY KEY("role_id");
ALTER TABLE
    "roles" ADD CONSTRAINT "roles_role_name_unique" UNIQUE("role_name");
CREATE TABLE "supervisor_profile"(
    "user_id(FK)" INTEGER NOT NULL,
    "school_name" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "supervisor_profile" ADD PRIMARY KEY("user_id(FK)");
CREATE TABLE "admin_profile"("admin_id (FK)" INTEGER NOT NULL);
ALTER TABLE
    "admin_profile" ADD PRIMARY KEY("admin_id (FK)");
CREATE TABLE "tracks"(
    "track_id" INTEGER NOT NULL,
    "track_name" VARCHAR(255) CHECK
        ("track_name" IN('')) NOT NULL,
        "state_id (FK)" INTEGER NOT NULL
);
ALTER TABLE
    "tracks" ADD PRIMARY KEY("track_id");
ALTER TABLE
    "tracks" ADD CONSTRAINT "tracks_track_name_unique" UNIQUE("track_name");
ALTER TABLE
    "tracks" ADD CONSTRAINT "tracks_state_id (fk)_unique" UNIQUE("state_id (FK)");
CREATE TABLE "role_assignment_history"(
    "assignment_id" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL,
    "role_id (FK)" INTEGER NOT NULL,
    "valid_from" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "valid_to" TIMESTAMP(0)
    WITH
        TIME zone NOT NULL
);
ALTER TABLE
    "role_assignment_history" ADD PRIMARY KEY("assignment_id");
ALTER TABLE
    "role_assignment_history" ADD CONSTRAINT "role_assignment_history_user_id (fk)_unique" UNIQUE("user_id (FK)");
ALTER TABLE
    "role_assignment_history" ADD CONSTRAINT "role_assignment_history_role_id (fk)_unique" UNIQUE("role_id (FK)");
ALTER TABLE
    "role_assignment_history" ADD CONSTRAINT "role_assignment_history_valid_from_unique" UNIQUE("valid_from");
CREATE TABLE "background"(
    "background_id" INTEGER NOT NULL,
    "background_desc (UNIQUE)" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "background" ADD PRIMARY KEY("background_id");
ALTER TABLE
    "background" ADD CONSTRAINT "background_background_desc (unique)_unique" UNIQUE("background_desc (UNIQUE)");
CREATE TABLE "countries"(
    "country_id" INTEGER NOT NULL,
    "country_name" CHAR(255) NOT NULL
);
ALTER TABLE
    "countries" ADD PRIMARY KEY("country_id");
CREATE TABLE "country_states"(
    "state_id" INTEGER NOT NULL,
    "country_id (FK)" INTEGER NOT NULL,
    "state_name" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "country_states" ADD PRIMARY KEY("state_id");
CREATE TABLE "areas_of_interest"(
    "interest_id" INTEGER NOT NULL,
    "interest_desc" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "areas_of_interest" ADD PRIMARY KEY("interest_id");
CREATE TABLE "relationship_type"(
    "relationship_type_id" INTEGER NOT NULL,
    "relationship_type" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "relationship_type" ADD PRIMARY KEY("relationship_type_id");
ALTER TABLE
    "relationship_type" ADD CONSTRAINT "relationship_type_relationship_type_unique" UNIQUE("relationship_type");
CREATE TABLE "sessions"(
    "session_id" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL,
    "access_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "isLoggedin" BOOLEAN NOT NULL
);
ALTER TABLE
    "sessions" ADD PRIMARY KEY("session_id");
CREATE TABLE "group_members"(
    "group_id (FK)" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL
);
ALTER TABLE
    "group_members" ADD PRIMARY KEY("group_id (FK)");
ALTER TABLE
    "group_members" ADD PRIMARY KEY("user_id (FK)");
CREATE TABLE "messages"(
    "message_id" BIGINT NOT NULL,
    "sender_user_id (FK)" BIGINT NOT NULL,
    "group_id (FK)" BIGINT NOT NULL,
    "message_text" VARCHAR(255) NOT NULL,
    "sent_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "deleted_flag" BOOLEAN NOT NULL
);
ALTER TABLE
    "messages" ADD PRIMARY KEY("message_id");
CREATE TABLE "message_attachments"(
    "attachment_id" BIGINT NOT NULL,
    "message_id" BIGINT NOT NULL,
    "attachment_filename" VARCHAR(255) NOT NULL
);
ALTER TABLE
    "message_attachments" ADD PRIMARY KEY("attachment_id");
ALTER TABLE
    "message_attachments" ADD PRIMARY KEY("message_id");
CREATE TABLE "tasks"(
    "task_id" INTEGER NOT NULL,
    "task_name" VARCHAR(255) NOT NULL,
    "due_date" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
    "deleted_flag" BOOLEAN NOT NULL,
    "milestone_id (FK)" INTEGER NOT NULL,
    "task_description" VARCHAR(255) NULL
);
ALTER TABLE
    "tasks" ADD PRIMARY KEY("task_id");
CREATE TABLE "events"(
    "event_id" INTEGER NOT NULL,
    "event_name" VARCHAR(255) NOT NULL,
    "description" VARCHAR(255) NULL,
    "start_datetime" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
    "ends_datetime" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
    "location" VARCHAR(255) NOT NULL,
    "humanitix_link" VARCHAR(255) NOT NULL,
    "host_user_id (FK)" INTEGER NOT NULL,
    "deleted_flag" BOOLEAN NOT NULL,
    "deleted_datetime" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
    "event_image(IMG)" VARCHAR(255) NULL,
    "is_virtual" BOOLEAN NOT NULL
);
ALTER TABLE
    "events" ADD PRIMARY KEY("event_id");
CREATE TABLE "workshops"(
    "workshop_id" INTEGER NOT NULL,
    "workshop_name" VARCHAR(255) NOT NULL,
    "start_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "duration" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,
        "location" VARCHAR(255) NOT NULL,
        "description" VARCHAR(255) NULL,
        "zoom_link" VARCHAR(255) NULL,
        "host_user_id (FK)" INTEGER NOT NULL,
        "group_id (FK)" INTEGER NOT NULL,
        "deleted_flag" BOOLEAN NOT NULL,
        "deleted_datetime" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL
);
ALTER TABLE
    "workshops" ADD PRIMARY KEY("workshop_id");
CREATE TABLE "workshop_attendance"(
    "workshop_id" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL,
    "responded" BOOLEAN NOT NULL
);
ALTER TABLE
    "workshop_attendance" ADD PRIMARY KEY("workshop_id");
ALTER TABLE
    "workshop_attendance" ADD PRIMARY KEY("user_id (FK)");
CREATE TABLE "student_interest"(
    "interest_id" INTEGER NOT NULL,
    "user_id" INTEGER NOT NULL
);
ALTER TABLE
    "student_interest" ADD PRIMARY KEY("interest_id");
ALTER TABLE
    "student_interest" ADD PRIMARY KEY("user_id");
CREATE TABLE "student_supervisor"(
    "student_user_id" INTEGER NOT NULL,
    "supervisor_user_id" INTEGER NOT NULL,
    "relationship_type_id" INTEGER NOT NULL
);
ALTER TABLE
    "student_supervisor" ADD PRIMARY KEY("student_user_id");
ALTER TABLE
    "student_supervisor" ADD PRIMARY KEY("supervisor_user_id");
CREATE TABLE "event_invite"(
    "event_id (FK)" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL,
    "sent_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "attendance_status" BOOLEAN NOT NULL,
        "rsvp_status" BOOLEAN NOT NULL
);
ALTER TABLE
    "event_invite" ADD PRIMARY KEY("event_id (FK)");
ALTER TABLE
    "event_invite" ADD PRIMARY KEY("user_id (FK)");
CREATE TABLE "milestone"(
    "milestone_id" INTEGER NOT NULL,
    "group_id (FK)" INTEGER NOT NULL,
    "milestone_name" VARCHAR(255) NOT NULL,
    "completed" BOOLEAN NOT NULL,
    "deleted_flag" BOOLEAN NOT NULL
);
ALTER TABLE
    "milestone" ADD PRIMARY KEY("milestone_id");
CREATE TABLE "task_assignees"(
    "task_id" INTEGER NOT NULL,
    "user_id" INTEGER NOT NULL,
    "assigned_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "deleted_flag" BOOLEAN NOT NULL
);
ALTER TABLE
    "task_assignees" ADD PRIMARY KEY("task_id");
ALTER TABLE
    "task_assignees" ADD PRIMARY KEY("user_id");
CREATE TABLE "alerts"(
    "alert_id" BIGINT NOT NULL,
    "session_id (FK)" BIGINT NOT NULL,
    "alert_timestamp" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "error_reason" VARCHAR(255) NOT NULL,
        "resolved" BOOLEAN NOT NULL
);
ALTER TABLE
    "alerts" ADD PRIMARY KEY("alert_id");
CREATE TABLE "resources"(
    "resource_id" INTEGER NOT NULL,
    "resource_name" VARCHAR(255) NULL,
    "resource_description" VARCHAR(255) NOT NULL,
    "upload_datetime" TIMESTAMP(0) WITH
        TIME zone NOT NULL,
        "uploader_user_id (FK)" INTEGER NOT NULL,
        "deleted_flag" BOOLEAN NOT NULL,
        "deleted_datetime" TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL
);
ALTER TABLE
    "resources" ADD PRIMARY KEY("resource_id");
CREATE TABLE "resource_roles"(
    "resource_id" INTEGER NOT NULL,
    "role_id" INTEGER NOT NULL
);
ALTER TABLE
    "resource_roles" ADD PRIMARY KEY("resource_id");
ALTER TABLE
    "resource_roles" ADD PRIMARY KEY("role_id");
CREATE TABLE "event_target_role"(
    "event_id (FK)" INTEGER NOT NULL,
    "role_id (FK)" INTEGER NOT NULL
);
ALTER TABLE
    "event_target_role" ADD PRIMARY KEY("event_id (FK)");
ALTER TABLE
    "event_target_role" ADD PRIMARY KEY("role_id (FK)");
CREATE TABLE "event_target_group"(
    "event_id (FK)" INTEGER NOT NULL,
    "group_id (FK)" INTEGER NOT NULL
);
ALTER TABLE
    "event_target_group" ADD PRIMARY KEY("event_id (FK)");
ALTER TABLE
    "event_target_group" ADD PRIMARY KEY("group_id (FK)");
CREATE TABLE "event_target_track"(
    "event_id (FK)" INTEGER NOT NULL,
    "track_id (FK)" INTEGER NOT NULL
);
ALTER TABLE
    "event_target_track" ADD PRIMARY KEY("event_id (FK)");
ALTER TABLE
    "event_target_track" ADD PRIMARY KEY("track_id (FK)");
CREATE TABLE "mentor_certificate"(
    "certificate_id" INTEGER NOT NULL,
    "certificate_type_id" INTEGER NOT NULL,
    "user_id (FK)" INTEGER NOT NULL,
    "certificate_number" VARCHAR(255) NULL,
    "issued_by" VARCHAR(255) NOT NULL,
    "issued_at" DATE NOT NULL,
    "expires_at" DATE NULL,
    "file_url" VARCHAR(255) NULL,
    "verified" BOOLEAN NOT NULL
);
ALTER TABLE
    "mentor_certificate" ADD PRIMARY KEY("certificate_id");
CREATE TABLE "certificate_type"(
    "certificate_type_id" INTEGER NOT NULL,
    "certificate_type" VARCHAR(255) CHECK
        ("certificate_type" IN('')) NOT NULL,
        "requires_number" BOOLEAN NOT NULL,
        "requires_expiry" BOOLEAN NOT NULL
);
ALTER TABLE
    "certificate_type" ADD PRIMARY KEY("certificate_type_id");
ALTER TABLE
    "certificate_type" ADD CONSTRAINT "certificate_type_certificate_type_unique" UNIQUE("certificate_type");
ALTER TABLE
    "users" ADD CONSTRAINT "users_track_id_foreign" FOREIGN KEY("track_id") REFERENCES "tracks"("track_id");
ALTER TABLE
    "events" ADD CONSTRAINT "events_event_id_foreign" FOREIGN KEY("event_id") REFERENCES "event_target_group"("event_id (FK)");
ALTER TABLE
    "groups" ADD CONSTRAINT "groups_group_id_foreign" FOREIGN KEY("group_id") REFERENCES "group_members"("group_id (FK)");
ALTER TABLE
    "tracks" ADD CONSTRAINT "tracks_track_id_foreign" FOREIGN KEY("track_id") REFERENCES "event_target_track"("track_id (FK)");
ALTER TABLE
    "messages" ADD CONSTRAINT "messages_message_id_foreign" FOREIGN KEY("message_id") REFERENCES "message_attachments"("message_id");
ALTER TABLE
    "groups" ADD CONSTRAINT "groups_group_id_foreign" FOREIGN KEY("group_id") REFERENCES "event_target_group"("group_id (FK)");
ALTER TABLE
    "roles" ADD CONSTRAINT "roles_role_id_foreign" FOREIGN KEY("role_id") REFERENCES "resource_roles"("role_id");
ALTER TABLE
    "country_states" ADD CONSTRAINT "country_states_country_id (fk)_foreign" FOREIGN KEY("country_id (FK)") REFERENCES "countries"("country_id");
ALTER TABLE
    "events" ADD CONSTRAINT "events_event_id_foreign" FOREIGN KEY("event_id") REFERENCES "event_invite"("event_id (FK)");
ALTER TABLE
    "events" ADD CONSTRAINT "events_host_user_id (fk)_foreign" FOREIGN KEY("host_user_id (FK)") REFERENCES "users"("user_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "mentor_profile"("user_id (FK)");
ALTER TABLE
    "workshops" ADD CONSTRAINT "workshops_group_id (fk)_foreign" FOREIGN KEY("group_id (FK)") REFERENCES "groups"("group_id");
ALTER TABLE
    "student_profile" ADD CONSTRAINT "student_profile_supervisor_id (fk)_foreign" FOREIGN KEY("supervisor_id (FK)") REFERENCES "supervisor_profile"("user_id(FK)");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "group_members"("user_id (FK)");
ALTER TABLE
    "alerts" ADD CONSTRAINT "alerts_session_id (fk)_foreign" FOREIGN KEY("session_id (FK)") REFERENCES "sessions"("session_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "supervisor_profile"("user_id(FK)");
ALTER TABLE
    "tracks" ADD CONSTRAINT "tracks_state_id (fk)_foreign" FOREIGN KEY("state_id (FK)") REFERENCES "country_states"("state_id");
ALTER TABLE
    "student_profile" ADD CONSTRAINT "student_profile_user_id (fk)_foreign" FOREIGN KEY("user_id (FK)") REFERENCES "student_supervisor"("student_user_id");
ALTER TABLE
    "student_profile" ADD CONSTRAINT "student_profile_interest_id (fk)_foreign" FOREIGN KEY("interest_id (FK)") REFERENCES "student_interest"("interest_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "task_assignees"("user_id");
ALTER TABLE
    "student_supervisor" ADD CONSTRAINT "student_supervisor_relationship_type_id_foreign" FOREIGN KEY("relationship_type_id") REFERENCES "relationship_type"("relationship_type_id");
ALTER TABLE
    "milestone" ADD CONSTRAINT "milestone_group_id (fk)_foreign" FOREIGN KEY("group_id (FK)") REFERENCES "groups"("group_id");
ALTER TABLE
    "supervisor_profile" ADD CONSTRAINT "supervisor_profile_user_id(fk)_foreign" FOREIGN KEY("user_id(FK)") REFERENCES "student_supervisor"("supervisor_user_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "student_profile"("user_id (FK)");
ALTER TABLE
    "mentor_profile" ADD CONSTRAINT "mentor_profile_background_id(fk)_foreign" FOREIGN KEY("background_id(FK)") REFERENCES "background"("background_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_state_id_foreign" FOREIGN KEY("state_id") REFERENCES "country_states"("state_id");
ALTER TABLE
    "messages" ADD CONSTRAINT "messages_sender_user_id (fk)_foreign" FOREIGN KEY("sender_user_id (FK)") REFERENCES "users"("user_id");
ALTER TABLE
    "role_assignment_history" ADD CONSTRAINT "role_assignment_history_role_id (fk)_foreign" FOREIGN KEY("role_id (FK)") REFERENCES "roles"("role_id");
ALTER TABLE
    "resources" ADD CONSTRAINT "resources_resource_id_foreign" FOREIGN KEY("resource_id") REFERENCES "resource_roles"("resource_id");
ALTER TABLE
    "events" ADD CONSTRAINT "events_event_id_foreign" FOREIGN KEY("event_id") REFERENCES "event_target_track"("event_id (FK)");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "event_invite"("user_id (FK)");
ALTER TABLE
    "task_assignees" ADD CONSTRAINT "task_assignees_task_id_foreign" FOREIGN KEY("task_id") REFERENCES "tasks"("task_id");
ALTER TABLE
    "groups" ADD CONSTRAINT "groups_track_id (fk)_foreign" FOREIGN KEY("track_id (FK)") REFERENCES "tracks"("track_id");
ALTER TABLE
    "tasks" ADD CONSTRAINT "tasks_milestone_id (fk)_foreign" FOREIGN KEY("milestone_id (FK)") REFERENCES "milestone"("milestone_id");
ALTER TABLE
    "role_assignment_history" ADD CONSTRAINT "role_assignment_history_user_id (fk)_foreign" FOREIGN KEY("user_id (FK)") REFERENCES "users"("user_id");
ALTER TABLE
    "sessions" ADD CONSTRAINT "sessions_user_id (fk)_foreign" FOREIGN KEY("user_id (FK)") REFERENCES "users"("user_id");
ALTER TABLE
    "events" ADD CONSTRAINT "events_event_id_foreign" FOREIGN KEY("event_id") REFERENCES "event_target_role"("event_id (FK)");
ALTER TABLE
    "workshops" ADD CONSTRAINT "workshops_host_user_id (fk)_foreign" FOREIGN KEY("host_user_id (FK)") REFERENCES "users"("user_id");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "student_interest"("user_id");
ALTER TABLE
    "roles" ADD CONSTRAINT "roles_role_id_foreign" FOREIGN KEY("role_id") REFERENCES "event_target_role"("role_id (FK)");
ALTER TABLE
    "messages" ADD CONSTRAINT "messages_group_id (fk)_foreign" FOREIGN KEY("group_id (FK)") REFERENCES "groups"("group_id");
ALTER TABLE
    "student_profile" ADD CONSTRAINT "student_profile_interest_id (fk)_foreign" FOREIGN KEY("interest_id (FK)") REFERENCES "areas_of_interest"("interest_id");
ALTER TABLE
    "mentor_certificate" ADD CONSTRAINT "mentor_certificate_certificate_type_id_foreign" FOREIGN KEY("certificate_type_id") REFERENCES "certificate_type"("certificate_type_id");
ALTER TABLE
    "workshops" ADD CONSTRAINT "workshops_workshop_id_foreign" FOREIGN KEY("workshop_id") REFERENCES "workshop_attendance"("workshop_id");
ALTER TABLE
    "mentor_certificate" ADD CONSTRAINT "mentor_certificate_user_id (fk)_foreign" FOREIGN KEY("user_id (FK)") REFERENCES "mentor_profile"("user_id (FK)");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "admin_profile"("admin_id (FK)");
ALTER TABLE
    "users" ADD CONSTRAINT "users_user_id_foreign" FOREIGN KEY("user_id") REFERENCES "workshop_attendance"("user_id (FK)");