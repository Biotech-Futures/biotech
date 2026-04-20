ALTER TABLE "resources" ADD COLUMN "resource_name" varchar(255);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "resource_description" varchar(1000);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "resource_type" varchar(50);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "resource_kind" varchar(20);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "content_html" text;--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "file_name" varchar(255);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "file_mime_type" varchar(100);--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "file_size" bigint;--> statement-breakpoint
ALTER TABLE "resources" ADD COLUMN "storage_key" varchar(500);--> statement-breakpoint

UPDATE "resources"
SET
  "resource_name" = COALESCE("resource_name", 'Resource ' || "id"),
  "resource_kind" = COALESCE("resource_kind", 'file'),
  "storage_key" = COALESCE("storage_key", 'resources/legacy-' || "id"::text || '.bin')
WHERE
  "resource_name" IS NULL
  OR "resource_kind" IS NULL
  OR "storage_key" IS NULL;--> statement-breakpoint

ALTER TABLE "resources" ALTER COLUMN "resource_name" SET NOT NULL;--> statement-breakpoint
ALTER TABLE "resources" ALTER COLUMN "resource_kind" SET NOT NULL;--> statement-breakpoint
ALTER TABLE "resources" ALTER COLUMN "storage_key" SET NOT NULL;--> statement-breakpoint
