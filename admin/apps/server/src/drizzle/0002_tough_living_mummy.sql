DELETE FROM "resource_audience";
--> statement-breakpoint
DELETE FROM "resources";
--> statement-breakpoint

ALTER TABLE "resources" DROP CONSTRAINT IF EXISTS "resources_uploader_user_id_fkey";
--> statement-breakpoint
ALTER TABLE "resources" ALTER COLUMN "uploader_user_id" TYPE text USING "uploader_user_id"::text;
--> statement-breakpoint
ALTER TABLE "resources" ADD CONSTRAINT "resources_uploader_user_id_fkey" FOREIGN KEY ("uploader_user_id") REFERENCES "public"."admin_user"("id") ON DELETE no action ON UPDATE no action;
