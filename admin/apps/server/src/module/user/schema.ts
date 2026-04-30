import { z } from "zod";

export const ROLES = ["student", "mentor", "supervisor", "admin"] as const;

const trackNameSchema = z.string().trim().min(1);
const interestListSchema = z.array(z.string().trim().min(1)).default([]);
// DB CHECK constraint: year_lvl IN ('9','10','11','12')
const yearLevelSchema = z.coerce.number().int().min(9).max(12);

export const queryUsersSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  role: z.enum(ROLES).optional(),
  track: trackNameSchema.optional(),
  active: z.coerce.boolean().optional(),
});

export const queryStudentsSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  limit: z.coerce.number().min(1).max(100).default(10),
  search: z.string().optional(),
  yearLevel: yearLevelSchema.optional(),
  track: z.string().optional(),
  interest: z.string().optional(),
  inGroup: z.enum(["yes", "no"]).optional(),
  active: z.coerce.boolean().optional(),
});

export const createUserSchema = z.object({
  firstName: z.string().min(1).max(255),
  lastName: z.string().min(1).max(255),
  email: z.string().email(),
  role: z.enum(ROLES),
  track: trackNameSchema.optional(),
  // Student-only fields
  schoolName: z.string().trim().max(255).optional(),
  yearLevel: yearLevelSchema.optional(),
  interests: interestListSchema.optional(),
  joinPermissionReceived: z.coerce.boolean().optional(),
  // Supervisor-only field
  supervisorSchoolName: z.string().trim().max(255).optional(),
  active: z.coerce.boolean().optional(),
});

export const bulkCreateUsersSchema = z.object({
  users: z.array(createUserSchema).min(1),
});

export const updateUserSchema = z.object({
  firstName: z.string().min(1).max(255).optional(),
  lastName: z.string().min(1).max(255).optional(),
  email: z.string().email().optional(),
  role: z.enum(ROLES).optional(),
  track: trackNameSchema.nullable().optional(),
  // Student-only fields
  schoolName: z.string().trim().max(255).nullable().optional(),
  yearLevel: yearLevelSchema.nullable().optional(),
  interests: interestListSchema.optional(),
  joinPermissionReceived: z.coerce.boolean().optional(),
  // Supervisor-only field
  supervisorSchoolName: z.string().trim().max(255).nullable().optional(),
  active: z.coerce.boolean().optional(),
});

export const updateStatusSchema = z.object({
  isActive: z.boolean(),
});

export type QueryUsersInput = z.infer<typeof queryUsersSchema>;
export type QueryStudentsInput = z.infer<typeof queryStudentsSchema>;
export type CreateUserInput = z.infer<typeof createUserSchema>;
export type BulkCreateUsersInput = z.infer<typeof bulkCreateUsersSchema>;
export type UpdateUserInput = z.infer<typeof updateUserSchema>;
export type UpdateStatusInput = z.infer<typeof updateStatusSchema>;
