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

export const replaceMentorSchema = z.object({
  membershipId: z.coerce.number().int().positive(),
  groupId: z.coerce.number().int().positive(),
  newMentorUserId: z.coerce.number().int().positive(),
});

export type ConfirmMentorAssignmentInput = z.infer<
  typeof confirmMentorAssignmentSchema
>;

export type MentorMatchUidQueryInput = z.infer<
  typeof mentorMatchUidQuerySchema
>;

export const unassignMentorsSchema = z.object({
  groupIds: z.array(z.coerce.number().int().positive()).min(1),
});

export type ReplaceMentorInput = z.infer<typeof replaceMentorSchema>;
export type UnassignMentorsInput = z.infer<typeof unassignMentorsSchema>;
