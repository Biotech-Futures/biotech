-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TABLE "admin_scope" (
	"id" bigint PRIMARY KEY NOT NULL,
	"user_id" bigint NOT NULL,
	"track_id" bigint,
	"is_global" boolean NOT NULL
);
--> statement-breakpoint
CREATE TABLE "alert" (
	"id" bigint PRIMARY KEY NOT NULL,
	"session_id" bigint NOT NULL,
	"created_at" timestamp(6) NOT NULL,
	"error_reason" varchar(255) NOT NULL,
	"resolved" boolean NOT NULL,
	"resolved_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "announcements" (
	"id" bigint PRIMARY KEY NOT NULL,
	"author_user_id" bigint NOT NULL,
	"track_id" bigint,
	"visibility_scope" varchar(50) NOT NULL,
	"published_at" timestamp(6) NOT NULL,
	"archived_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "announcement_audience" (
	"id" bigint PRIMARY KEY NOT NULL,
	"announcement_id" bigint NOT NULL,
	"role_id" bigint,
	"track_id" bigint
);
--> statement-breakpoint
CREATE TABLE "areas_of_interest" (
	"id" bigint PRIMARY KEY NOT NULL,
	"interest_desc" varchar(255) NOT NULL,
	CONSTRAINT "areas_of_interest_interest_desc_key" UNIQUE("interest_desc")
);
--> statement-breakpoint
CREATE TABLE "countries" (
	"id" bigint PRIMARY KEY NOT NULL,
	"country_name" varchar(255) NOT NULL,
	CONSTRAINT "countries_country_name_key" UNIQUE("country_name")
);
--> statement-breakpoint
CREATE TABLE "match_run" (
	"id" bigint PRIMARY KEY NOT NULL,
	"admin_user_id" text NOT NULL,
	"run_type" varchar(100) NOT NULL,
	"payload" jsonb NOT NULL,
	"created_at" timestamp(6) NOT NULL,
	"result" jsonb NOT NULL
);
--> statement-breakpoint
CREATE TABLE "mentor_profile" (
	"user_id" bigint PRIMARY KEY NOT NULL,
	"institution" varchar(255),
	"max_group_count" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE "mentor_interest" (
	"id" bigint PRIMARY KEY NOT NULL,
	"mentor_user_id" bigint NOT NULL,
	"interest_id" bigint NOT NULL
);
--> statement-breakpoint
CREATE TABLE "resource_audience" (
	"id" bigint PRIMARY KEY NOT NULL,
	"resource_id" bigint NOT NULL,
	"role_id" bigint,
	"track_id" bigint
);
--> statement-breakpoint
CREATE TABLE "events" (
	"id" bigint PRIMARY KEY NOT NULL,
	"host_user_id" bigint,
	"track_id" bigint,
	"event_type" varchar(100),
	"start_at" timestamp(6) NOT NULL,
	"ends_at" timestamp(6) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "event_rsvp" (
	"id" bigint PRIMARY KEY NOT NULL,
	"event_id" bigint NOT NULL,
	"user_id" bigint NOT NULL,
	"rsvp_status" varchar(50) NOT NULL,
	"responded_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "groups" (
	"id" bigint PRIMARY KEY NOT NULL,
	"group_name" varchar(255) NOT NULL,
	"track_id" bigint NOT NULL,
	"created_at" timestamp(6) NOT NULL,
	"deleted_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "group_membership" (
	"id" bigint PRIMARY KEY NOT NULL,
	"group_id" bigint NOT NULL,
	"user_id" bigint NOT NULL,
	"membership_role" varchar(50),
	"joined_at" timestamp(6) NOT NULL,
	"left_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "mentor_availability" (
	"id" bigint PRIMARY KEY NOT NULL,
	"mentor_user_id" bigint NOT NULL,
	"weekday" smallint NOT NULL,
	"start_time" time(6) NOT NULL,
	"end_time" time(6) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "certificate_type" (
	"id" bigint PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"requires_number" boolean NOT NULL,
	"requires_expiry" boolean NOT NULL,
	CONSTRAINT "certificate_type_name_key" UNIQUE("name")
);
--> statement-breakpoint
CREATE TABLE "mentor_certificate" (
	"id" bigint PRIMARY KEY NOT NULL,
	"mentor_profile_id" bigint NOT NULL,
	"certificate_type_id" bigint NOT NULL,
	"certificate_number" varchar(255),
	"issued_by" varchar(255),
	"issued_at" date NOT NULL,
	"expires_at" date,
	"file_url" varchar(500),
	"verified_at" timestamp(6),
	"verified_by_user_id" bigint
);
--> statement-breakpoint
CREATE TABLE "messages" (
	"id" bigint PRIMARY KEY NOT NULL,
	"group_id" bigint NOT NULL,
	"sender_user_id" bigint NOT NULL,
	"message_text" text NOT NULL,
	"sent_at" timestamp(6) NOT NULL,
	"edited_at" timestamp(6),
	"deleted_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "student_interest" (
	"id" bigint PRIMARY KEY NOT NULL,
	"student_user_id" bigint NOT NULL,
	"interest_id" bigint NOT NULL
);
--> statement-breakpoint
CREATE TABLE "supervisor_profile" (
	"user_id" bigint PRIMARY KEY NOT NULL,
	"school_name" varchar(255) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "roles" (
	"id" bigint PRIMARY KEY NOT NULL,
	"slug" varchar(100) NOT NULL,
	CONSTRAINT "roles_slug_key" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "verification" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp(6) NOT NULL,
	"created_at" timestamp(6) DEFAULT now() NOT NULL,
	"updated_at" timestamp(6) DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "admin_user" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"email" text NOT NULL,
	"email_verified" boolean DEFAULT false NOT NULL,
	"image" text,
	"created_at" timestamp(6) DEFAULT now() NOT NULL,
	"updated_at" timestamp(6) DEFAULT now() NOT NULL,
	CONSTRAINT "user_email_key" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "account" (
	"id" text PRIMARY KEY NOT NULL,
	"account_id" text NOT NULL,
	"provider_id" text NOT NULL,
	"user_id" text NOT NULL,
	"access_token" text,
	"refresh_token" text,
	"id_token" text,
	"access_token_expires_at" timestamp(6),
	"refresh_token_expires_at" timestamp(6),
	"scope" text,
	"password" text,
	"created_at" timestamp(6) DEFAULT now() NOT NULL,
	"updated_at" timestamp(6) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tracks" (
	"id" bigint PRIMARY KEY NOT NULL,
	"track_code" varchar(100) NOT NULL,
	"state_id" bigint NOT NULL,
	CONSTRAINT "tracks_track_code_key" UNIQUE("track_code")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" bigint PRIMARY KEY NOT NULL,
	"email" varchar(255) NOT NULL,
	"first_name" varchar(255) NOT NULL,
	"last_name" varchar(255) NOT NULL,
	"is_active" boolean NOT NULL,
	"track_id" bigint NOT NULL,
	"account_status" varchar(50) NOT NULL,
	"invited_at" timestamp(6),
	"activated_at" timestamp(6),
	"admin_user_id" varchar(255),
	CONSTRAINT "users_email_key" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "user_session" (
	"id" bigint PRIMARY KEY NOT NULL,
	"user_id" bigint NOT NULL,
	"created_at" timestamp(6) NOT NULL,
	"last_activity_at" timestamp(6),
	"expires_at" timestamp(6) NOT NULL,
	"ended_at" timestamp(6),
	"revoked_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "audit_log" (
	"id" bigint PRIMARY KEY NOT NULL,
	"actor_user_id" bigint,
	"entity_type" varchar(100) NOT NULL,
	"entity_id" bigint NOT NULL,
	"action" varchar(100) NOT NULL,
	"before_state" jsonb,
	"after_state" jsonb,
	"created_at" timestamp(6) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "country_states" (
	"id" bigint PRIMARY KEY NOT NULL,
	"country_id" bigint NOT NULL,
	"state_name" varchar(255) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "resources" (
	"id" bigint PRIMARY KEY NOT NULL,
	"uploader_user_id" bigint NOT NULL,
	"track_id" bigint,
	"visibility_scope" varchar(50) NOT NULL,
	"uploaded_at" timestamp(6) NOT NULL,
	"deleted_at" timestamp(6)
);
--> statement-breakpoint
CREATE TABLE "session" (
	"id" text PRIMARY KEY NOT NULL,
	"expires_at" timestamp(6) NOT NULL,
	"token" text NOT NULL,
	"created_at" timestamp(6) DEFAULT now() NOT NULL,
	"updated_at" timestamp(6) NOT NULL,
	"ip_address" text,
	"user_agent" text,
	"user_id" text NOT NULL,
	CONSTRAINT "session_token_key" UNIQUE("token")
);
--> statement-breakpoint
CREATE TABLE "student_profile" (
	"user_id" bigint PRIMARY KEY NOT NULL,
	"supervisor_user_id" bigint,
	"school_name" varchar(255),
	"year_level" smallint,
	"join_permission_received" boolean NOT NULL,
	"join_permission_response_id" varchar(255)
);
--> statement-breakpoint
CREATE TABLE "user_role_assignment" (
	"id" bigint PRIMARY KEY NOT NULL,
	"user_id" bigint NOT NULL,
	"role_id" bigint NOT NULL,
	"valid_from" timestamp(6) NOT NULL,
	"valid_to" timestamp(6)
);
--> statement-breakpoint
ALTER TABLE "admin_scope" ADD CONSTRAINT "admin_scope_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "admin_scope" ADD CONSTRAINT "admin_scope_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "alert" ADD CONSTRAINT "alert_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."user_session"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcements" ADD CONSTRAINT "announcements_author_user_id_fkey" FOREIGN KEY ("author_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcements" ADD CONSTRAINT "announcements_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcement_audience" ADD CONSTRAINT "announcement_audience_announcement_id_fkey" FOREIGN KEY ("announcement_id") REFERENCES "public"."announcements"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcement_audience" ADD CONSTRAINT "announcement_audience_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcement_audience" ADD CONSTRAINT "announcement_audience_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "match_run" ADD CONSTRAINT "match_run_initiated_by_user_id_fkey" FOREIGN KEY ("admin_user_id") REFERENCES "public"."admin_user"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_interest" ADD CONSTRAINT "mentor_interest_interest_id_fkey" FOREIGN KEY ("interest_id") REFERENCES "public"."areas_of_interest"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_interest" ADD CONSTRAINT "mentor_interest_mentor_user_id_fkey" FOREIGN KEY ("mentor_user_id") REFERENCES "public"."mentor_profile"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resource_audience" ADD CONSTRAINT "resource_audience_resource_id_fkey" FOREIGN KEY ("resource_id") REFERENCES "public"."resources"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resource_audience" ADD CONSTRAINT "resource_audience_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resource_audience" ADD CONSTRAINT "resource_audience_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "events" ADD CONSTRAINT "events_host_user_id_fkey" FOREIGN KEY ("host_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "events" ADD CONSTRAINT "events_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_rsvp" ADD CONSTRAINT "event_rsvp_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_rsvp" ADD CONSTRAINT "event_rsvp_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "groups" ADD CONSTRAINT "groups_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "group_membership" ADD CONSTRAINT "group_membership_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "public"."groups"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "group_membership" ADD CONSTRAINT "group_membership_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_availability" ADD CONSTRAINT "mentor_availability_mentor_user_id_fkey" FOREIGN KEY ("mentor_user_id") REFERENCES "public"."mentor_profile"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_certificate" ADD CONSTRAINT "mentor_certificate_certificate_type_id_fkey" FOREIGN KEY ("certificate_type_id") REFERENCES "public"."certificate_type"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_certificate" ADD CONSTRAINT "mentor_certificate_mentor_profile_id_fkey" FOREIGN KEY ("mentor_profile_id") REFERENCES "public"."mentor_profile"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mentor_certificate" ADD CONSTRAINT "mentor_certificate_verified_by_user_id_fkey" FOREIGN KEY ("verified_by_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "public"."groups"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_sender_user_id_fkey" FOREIGN KEY ("sender_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "student_interest" ADD CONSTRAINT "student_interest_interest_id_fkey" FOREIGN KEY ("interest_id") REFERENCES "public"."areas_of_interest"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "student_interest" ADD CONSTRAINT "student_interest_student_user_id_fkey" FOREIGN KEY ("student_user_id") REFERENCES "public"."student_profile"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account" ADD CONSTRAINT "account_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."admin_user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tracks" ADD CONSTRAINT "tracks_state_id_fkey" FOREIGN KEY ("state_id") REFERENCES "public"."country_states"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_admin_user_id_user_id_fk" FOREIGN KEY ("admin_user_id") REFERENCES "public"."admin_user"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_session" ADD CONSTRAINT "user_session_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_log" ADD CONSTRAINT "audit_log_actor_user_id_fkey" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "country_states" ADD CONSTRAINT "country_states_country_id_fkey" FOREIGN KEY ("country_id") REFERENCES "public"."countries"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resources" ADD CONSTRAINT "resources_track_id_fkey" FOREIGN KEY ("track_id") REFERENCES "public"."tracks"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resources" ADD CONSTRAINT "resources_uploader_user_id_fkey" FOREIGN KEY ("uploader_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "session" ADD CONSTRAINT "session_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."admin_user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "student_profile" ADD CONSTRAINT "student_profile_supervisor_user_id_fkey" FOREIGN KEY ("supervisor_user_id") REFERENCES "public"."supervisor_profile"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_role_assignment" ADD CONSTRAINT "user_role_assignment_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_role_assignment" ADD CONSTRAINT "user_role_assignment_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "verification_identifier_idx" ON "verification" USING btree ("identifier" text_ops);--> statement-breakpoint
CREATE INDEX "account_userId_idx" ON "account" USING btree ("user_id" text_ops);--> statement-breakpoint
CREATE INDEX "session_userId_idx" ON "session" USING btree ("user_id" text_ops);
*/