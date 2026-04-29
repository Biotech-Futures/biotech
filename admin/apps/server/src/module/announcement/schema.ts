import { z } from "zod";

const visibilityScopeSchema = z.enum(["global", "track_based", "role_based"]);

export const queryAnnouncementsSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  archived: z
    .enum(["true", "false"])
    .transform((v) => v === "true")
    .optional(),
});

export const createAnnouncementSchema = z.object({
  title: z.string().min(1).max(255),
  body: z.string().min(1),
  visibility_scope: visibilityScopeSchema.default("global"),
  track_id: z.number().optional(),
  role_ids: z.array(z.number()).optional(),
  send_email: z.boolean().default(true),
});

export const updateAnnouncementSchema = z.object({
  title: z.string().min(1).max(255).optional(),
  body: z.string().min(1).optional(),
  visibility_scope: visibilityScopeSchema.optional(),
  track_id: z.number().nullable().optional(),
  role_ids: z.array(z.number()).optional(),
  send_email: z.boolean().optional(),
});

export type QueryAnnouncementsInput = z.infer<typeof queryAnnouncementsSchema>;
export type CreateAnnouncementInput = z.infer<typeof createAnnouncementSchema>;
export type UpdateAnnouncementInput = z.infer<typeof updateAnnouncementSchema>;
