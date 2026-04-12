import { z } from "zod";

export const roles = ["student", "mentor", "admin"] as const;
export const tracks = ["frontend", "backend", "fullstack", "data"] as const;

export const createUserSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  email: z.string().email("Please enter a valid email"),
  role: z.enum(roles),
  track: z.enum(tracks).nullable(),
  groupId: z.string().nullable(),
});

export const updateUserSchema = createUserSchema.partial();

export type CreateUser = z.infer<typeof createUserSchema>;
export type UpdateUser = z.infer<typeof updateUserSchema>;
