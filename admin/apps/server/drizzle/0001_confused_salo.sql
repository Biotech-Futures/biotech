CREATE SCHEMA "admin_user";
--> statement-breakpoint
ALTER TABLE "match_recommendation" DISABLE ROW LEVEL SECURITY;--> statement-breakpoint
DROP TABLE "match_recommendation" CASCADE;--> statement-breakpoint
ALTER TABLE "admin_user"."session" DROP CONSTRAINT "session_token_unique";--> statement-breakpoint
ALTER TABLE "admin_user"."user" DROP CONSTRAINT "user_email_unique";--> statement-breakpoint
ALTER TABLE "users" DROP CONSTRAINT "users_track_id_fkey";
--> statement-breakpoint
ALTER TABLE "users" DROP CONSTRAINT "users_id_fkey";
--> statement-breakpoint
ALTER TABLE "users" DROP CONSTRAINT "users_id_fkey1";
--> statement-breakpoint
ALTER TABLE "users" DROP CONSTRAINT "users_id_fkey2";
--> statement-breakpoint
DROP INDEX "country_states_country_id_state_name_idx";--> statement-breakpoint
DROP INDEX "mentor_availability_mentor_user_id_weekday_start_time_end_t_idx";--> statement-breakpoint
DROP INDEX "mentor_interest_mentor_user_id_interest_id_idx";--> statement-breakpoint
DROP INDEX "user_role_assignment_user_id_role_id_valid_from_idx";--> statement-breakpoint
DROP INDEX "admin_user"."account_userId_idx";--> statement-breakpoint
DROP INDEX "admin_user"."session_userId_idx";--> statement-breakpoint
DROP INDEX "admin_user"."verification_identifier_idx";--> statement-breakpoint
ALTER TABLE "match_run" ADD COLUMN "payload" jsonb;--> statement-breakpoint
ALTER TABLE "match_run" ADD COLUMN "result" jsonb;--> statement-breakpoint
CREATE INDEX "account_userId_idx" ON "admin_user"."account" USING btree ("user_id" text_ops);--> statement-breakpoint
CREATE INDEX "session_userId_idx" ON "admin_user"."session" USING btree ("user_id" text_ops);--> statement-breakpoint
CREATE INDEX "verification_identifier_idx" ON "admin_user"."verification" USING btree ("identifier" text_ops);--> statement-breakpoint
ALTER TABLE "admin_user"."session" ADD CONSTRAINT "session_token_key" UNIQUE("token");--> statement-breakpoint
ALTER TABLE "admin_user"."user" ADD CONSTRAINT "user_email_key" UNIQUE("email");