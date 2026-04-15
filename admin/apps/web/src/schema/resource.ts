import { z } from "zod";

const resourceTypeSchema = z.enum(["document", "guide", "video", "template"]);

export const createResourceSchema = z.object({
  resource_name: z.string().min(1, "Resource name is required").max(255),
  resource_description: z
    .string()
    .min(1, "Resource description is required")
    .max(1000),
  resource_type: resourceTypeSchema.optional(),
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
  track_id: z.number().nullable().optional(),
  role_ids: z.array(z.number()).optional(),
});

export type CreateResource = z.infer<typeof createResourceSchema>;
export type UpdateResource = z.infer<typeof updateResourceSchema>;
