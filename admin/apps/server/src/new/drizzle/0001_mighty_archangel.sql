ALTER TABLE "resources" ADD COLUMN "file_mime_type" varchar(100);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "file_name" varchar(255);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "file_size" bigint;--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "group_id" bigint;--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "resource_kind" varchar(20) DEFAULT 'file' NOT NULL;--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "storage_key" varchar(500);--> statement-breakpoint
ALTER TABLE "resources" ADD CONSTRAINT "resources_group_id_fk_groups_id" FOREIGN KEY ("group_id") REFERENCES "public"."groups"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "resources_group_id_idx" ON "resources" USING btree ("group_id" int8_ops);