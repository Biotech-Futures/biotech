import { z } from "zod";

export const confirmMatchAssignmentItemSchema = z.object({
  studentId: z.coerce.number().int().positive(),
  groupId: z.coerce.number().int().positive(),
});

export const confirmMatchAssignmentSchema = z.object({
  assignments: z.array(confirmMatchAssignmentItemSchema).min(1),
});

export type ConfirmMatchAssignmentInput = z.infer<
  typeof confirmMatchAssignmentSchema
>;
