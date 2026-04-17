import { z } from "zod";

export const matchUidQuerySchema = z.object({
  uid: z.coerce.number().int().positive(),
});

export const confirmMatchAssignmentItemSchema = z.object({
  studentId: z.coerce.number().int().positive(),
  groupId: z.union([z.coerce.number().int().positive(), z.string().min(1)]),
});

export const confirmMatchAssignmentSchema = z.object({
  assignments: z.array(confirmMatchAssignmentItemSchema).min(1),
});

export type ConfirmMatchAssignmentInput = z.infer<
  typeof confirmMatchAssignmentSchema
>;

export type MatchUidQueryInput = z.infer<typeof matchUidQuerySchema>;
