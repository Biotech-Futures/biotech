import type { z } from "zod";
import type {
  unmatchedGroupSchema,
  recommendedMentorSchema,
  mentorGroupRecommendationSchema,
  mentorScoreBreakdownSchema,
  confirmMentorAssignmentsResponseSchema,
  groupStudentSchema,
  mentorListItemSchema,
  matchedGroupMentorSchema,
  matchedGroupSchema,
} from "@/schema/mentorMatch";

export type GroupStudent = z.infer<typeof groupStudentSchema>;
export type MentorListItem = z.infer<typeof mentorListItemSchema>;
export type UnmatchedGroup = z.infer<typeof unmatchedGroupSchema>;
export type RecommendedMentor = z.infer<typeof recommendedMentorSchema>;
export type MentorScoreBreakdown = z.infer<typeof mentorScoreBreakdownSchema>;
export type MentorGroupRecommendation = z.infer<
  typeof mentorGroupRecommendationSchema
>;
export type ConfirmMentorAssignmentsResponse = z.infer<
  typeof confirmMentorAssignmentsResponseSchema
>;
export type MatchedGroupMentor = z.infer<typeof matchedGroupMentorSchema>;
export type MatchedGroup = z.infer<typeof matchedGroupSchema>;
