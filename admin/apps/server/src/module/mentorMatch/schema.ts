import { z } from "zod";

export const mentorMatchUidQuerySchema = z.object({
  uid: z.coerce.number().int().positive(),
});

export const confirmMentorAssignmentItemSchema = z.object({
  groupId: z.coerce.number().int().positive(),
  mentorUserId: z.coerce.number().int().positive(),
});

export const confirmMentorAssignmentSchema = z.object({
  assignments: z.array(confirmMentorAssignmentItemSchema).min(1),
});

export type ConfirmMentorAssignmentInput = z.infer<
  typeof confirmMentorAssignmentSchema
>;

export type MentorMatchUidQueryInput = z.infer<
  typeof mentorMatchUidQuerySchema
>;
