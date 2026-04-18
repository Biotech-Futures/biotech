import { z } from "zod";

const resourceTypeSchema = z.enum(["document", "guide", "video", "template"]);
const resourceKindSchema = z.enum(["file", "page"]);

export const queryResourcesSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  uploader: z.string().optional(),
  uploader_user_id: z.coerce.number().optional(),
  track_id: z.coerce.number().optional(),
  resource_type: resourceTypeSchema.optional(),
  resource_kind: resourceKindSchema.optional(),
  role_slug: z.string().optional(),
  order: z.enum(["newest", "oldest"]).default("newest"),
});

export const createResourceSchema = z.object({
  resource_name: z.string().min(1).max(255),
  resource_description: z.string().min(1).max(1000),
  resource_type: resourceTypeSchema.optional(),
  resource_kind: resourceKindSchema.default("file"),
  content_html: z.string().max(20000).nullable().optional(),
  track_id: z.number().optional(),
  role_ids: z.array(z.number()).optional(),
});

export const updateResourceSchema = z.object({
  resource_name: z.string().min(1).max(255).optional(),
  resource_description: z.string().min(1).max(1000).optional(),
  resource_type: resourceTypeSchema.nullable().optional(),
  resource_kind: resourceKindSchema.optional(),
  content_html: z.string().max(20000).nullable().optional(),
  track_id: z.number().nullable().optional(),
  role_ids: z.array(z.number()).optional(),
});

export const updateResourceRoleSchema = z.object({
  role_id: z.number().int().positive(),
});

export type QueryResourcesInput = z.infer<typeof queryResourcesSchema>;
export type CreateResourceInput = z.infer<typeof createResourceSchema>;
export type UpdateResourceInput = z.infer<typeof updateResourceSchema>;
export type UpdateResourceRoleInput = z.infer<typeof updateResourceRoleSchema>;
