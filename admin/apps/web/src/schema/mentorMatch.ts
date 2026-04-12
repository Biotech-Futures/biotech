import { z } from "zod";

// ─── Unmatched groups ────────────────────────────────────────────────────────

export const unmatchedGroupSchema = z.object({
  groupId: z.number(),
  groupName: z.string(),
  trackCode: z.string(),
});

export const unmatchedGroupsResponseSchema = z.object({
  data: z.array(unmatchedGroupSchema),
});

// ─── Mentor match recommendations ────────────────────────────────────────────

export const mentorScoreBreakdownSchema = z.object({
  baseScore: z.number(),
  trackPenalty: z.number(),
  interestBonus: z.number(),
  timezonePenalty: z.number(),
  capacityBonus: z.number(),
  objectiveScore: z.number(),
});

export const recommendedMentorSchema = z.object({
  mentorId: z.number(),
  name: z.string(),
  trackCode: z.string(),
  institution: z.string().nullable(),
  interests: z.array(z.string()),
  remainingCapacity: z.number(),
});

export const mentorGroupRecommendationSchema = z.object({
  group: z.object({
    groupId: z.number(),
    groupName: z.string(),
    trackCode: z.string(),
    studentInterests: z.array(z.string()),
    studentCount: z.number(),
  }),
  recommendedMentor: recommendedMentorSchema.nullable(),
  reason: z.string(),
  score: z.number(),
  scoreBreakdown: mentorScoreBreakdownSchema,
});

export const mentorMatchResponseSchema = z.object({
  data: z.array(mentorGroupRecommendationSchema),
});

// ─── Confirm response ────────────────────────────────────────────────────────

export const confirmMentorAssignmentsResponseSchema = z.object({
  msg: z.string(),
  data: z.object({
    confirmedCount: z.number().int().nonnegative(),
  }),
});

