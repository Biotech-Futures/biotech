import { z } from "zod";

export const queryResourcesSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  type: z.string().optional(),
  role: z.string().optional(),
  order: z.enum(["newest", "oldest", "name"]).default("newest"),
});

export const createResourceSchema = z.object({
  resource_name: z.string().min(1).max(255),
  resource_description: z.string().min(1).max(500),
  resource_type_id: z.string().optional(),
  role_ids: z.array(z.string()).optional(),
});

export const updateResourceSchema = z.object({
  resource_name: z.string().min(1).max(255).optional(),
  resource_description: z.string().min(1).max(500).optional(),
  resource_type_id: z.string().nullable().optional(),
  role_ids: z.array(z.string()).optional(),
});

export const updateResourceRoleSchema = z.object({
  role_id: z.string().min(1),
});

export type QueryResourcesInput = z.infer<typeof queryResourcesSchema>;
export type CreateResourceInput = z.infer<typeof createResourceSchema>;
export type UpdateResourceInput = z.infer<typeof updateResourceSchema>;
export type UpdateResourceRoleInput = z.infer<typeof updateResourceRoleSchema>;
