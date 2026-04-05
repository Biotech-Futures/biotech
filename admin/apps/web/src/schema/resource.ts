import { z } from "zod";

export const createResourceSchema = z.object({
  resource_name: z.string().min(1, "Resource name is required").max(255),
  resource_description: z
    .string()
    .min(1, "Resource description is required")
    .max(500),
  resource_type_id: z.string().optional(),
  role_ids: z.array(z.string()).optional(),
});

export const updateResourceSchema = z.object({
  resource_name: z.string().min(1, "Resource name is required").max(255).optional(),
  resource_description: z
    .string()
    .min(1, "Resource description is required")
    .max(500)
    .optional(),
  resource_type_id: z.string().nullable().optional(),
  role_ids: z.array(z.string()).optional(),
});

export type CreateResource = z.infer<typeof createResourceSchema>;
export type UpdateResource = z.infer<typeof updateResourceSchema>;
