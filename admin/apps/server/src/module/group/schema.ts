// Group validation schemas
import { z } from "zod";

export const queryGroupsSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  searchName: z.string().optional(), // Search by member name
  searchGroup: z.string().optional(), // Search by group name
  track: z.string().optional(),
});

export const updateGroupSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  track: z.string().optional(),
});

export type QueryGroupsInput = z.infer<typeof queryGroupsSchema>;
export type UpdateGroupInput = z.infer<typeof updateGroupSchema>;
