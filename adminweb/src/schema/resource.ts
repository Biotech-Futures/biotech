import { z } from "zod";

const resourceTypeSchema = z.enum(["document", "guide", "video", "template"]);
const resourceKindSchema = z.enum(["attachment", "file", "page"]);
const visibilityScopeSchema = z.enum(["global", "track_based", "role_based"]);

export const createResourceSchema = z.object({
  resource_name: z.string().min(1, "Resource name is required").max(255),
  resource_description: z
    .string()
    .min(1, "Resource description is required")
    .max(1000),
  resource_type: resourceTypeSchema.optional(),
  resource_kind: resourceKindSchema.default("file"),
  content_html: z.string().max(20000).nullable().optional(),
  visibility_scope: visibilityScopeSchema.default("global"),
  track_id: z.number().optional(),
  role_ids: z.array(z.number()).optional(),
});

export const updateResourceSchema = z.object({
  resource_name: z.string().min(1, "Resource name is required").max(255).optional(),
  resource_description: z
    .string()
    .min(1, "Resource description is required")
    .max(1000)
    .optional(),
  resource_type: resourceTypeSchema.nullable().optional(),
  resource_kind: resourceKindSchema.optional(),
  content_html: z.string().max(20000).nullable().optional(),
  visibility_scope: visibilityScopeSchema.optional(),
  track_id: z.number().nullable().optional(),
  role_ids: z.array(z.number()).optional(),
});

export type CreateResource = z.infer<typeof createResourceSchema>;
export type UpdateResource = z.infer<typeof updateResourceSchema>;
