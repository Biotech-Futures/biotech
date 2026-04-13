import { z } from "zod";

export const ROLES = ["student", "mentor", "admin"] as const;
export const TRACKS = ["frontend", "backend", "fullstack", "data"] as const;

export const queryUsersSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  role: z.enum(ROLES).optional(),
  track: z.enum(TRACKS).optional(),
});

export const queryStudentsSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  age: z.coerce.number().int().min(10).max(30).optional(),
  track: z.enum(TRACKS).optional(),
  interest: z.string().optional(),
  inGroup: z.enum(["yes", "no"]).optional(),
});

export const createUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum(ROLES),
  track: z.enum(TRACKS).optional(),
  groupId: z.string().optional(),
});

export const bulkCreateUsersSchema = z.object({
  users: z.array(createUserSchema).min(1),
});

export const updateUserSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  email: z.string().email().optional(),
  role: z.enum(ROLES).optional(),
  track: z.enum(TRACKS).nullable().optional(),
  groupId: z.string().nullable().optional(),
});

export type QueryUsersInput = z.infer<typeof queryUsersSchema>;
export type QueryStudentsInput = z.infer<typeof queryStudentsSchema>;
export type CreateUserInput = z.infer<typeof createUserSchema>;
export type BulkCreateUsersInput = z.infer<typeof bulkCreateUsersSchema>;
export type UpdateUserInput = z.infer<typeof updateUserSchema>;
