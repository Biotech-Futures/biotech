import type { z } from "zod";
import type {
  unmatchedGroupSchema,
  recommendedMentorSchema,
  mentorGroupRecommendationSchema,
  mentorScoreBreakdownSchema,
  confirmMentorAssignmentsResponseSchema,
  groupStudentSchema,
} from "@/schema/mentorMatch";

export type GroupStudent = z.infer<typeof groupStudentSchema>;
export type UnmatchedGroup = z.infer<typeof unmatchedGroupSchema>;
export type RecommendedMentor = z.infer<typeof recommendedMentorSchema>;
export type MentorScoreBreakdown = z.infer<typeof mentorScoreBreakdownSchema>;
export type MentorGroupRecommendation = z.infer<
  typeof mentorGroupRecommendationSchema
>;
export type ConfirmMentorAssignmentsResponse = z.infer<
  typeof confirmMentorAssignmentsResponseSchema
>;
