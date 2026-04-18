// Group validation schemas
import { z } from "zod";

export const queryGroupsSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  searchName: z.string().optional(), // Search by member name
  searchGroup: z.string().optional(), // Search by group name
  track: z.string().optional(),
  mentorStatus: z.enum(["matched", "unmatched"]).optional(),
});

export const updateGroupSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  track: z.string().optional(),
});

export const queryGroupMessagesSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(50),
});

export type QueryGroupsInput = z.infer<typeof queryGroupsSchema>;
export type QueryGroupMessagesInput = z.infer<typeof queryGroupMessagesSchema>;
export type UpdateGroupInput = z.infer<typeof updateGroupSchema>;
