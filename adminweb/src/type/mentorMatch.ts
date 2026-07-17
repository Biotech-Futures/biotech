import type { z } from "zod";
import type {
  unmatchedGroupSchema,
  mentorGroupRecommendationSchema,
  mentorListItemSchema,
  matchedGroupSchema,
} from "@/schema/mentorMatch";

export type MentorListItem = z.infer<typeof mentorListItemSchema>;
export type UnmatchedGroup = z.infer<typeof unmatchedGroupSchema>;
export type MentorGroupRecommendation = z.infer<
  typeof mentorGroupRecommendationSchema
>;
export type MatchedGroup = z.infer<typeof matchedGroupSchema>;
