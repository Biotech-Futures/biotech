import { z } from "zod";

export const confirmMentorAssignmentItemSchema = z.object({
  recommendationId: z.coerce.number().int().positive(),
});

export const confirmMentorAssignmentSchema = z.object({
  assignments: z.array(confirmMentorAssignmentItemSchema).min(1),
});

export type ConfirmMentorAssignmentInput = z.infer<
  typeof confirmMentorAssignmentSchema
>;
