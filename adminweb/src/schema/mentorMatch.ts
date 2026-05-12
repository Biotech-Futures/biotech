import { z } from "zod";

// ─── Shared sub-schemas ───────────────────────────────────────────────────────

export const groupStudentSchema = z.object({
  name: z.string(),
  interests: z.array(z.string()),
});

// ─── Unmatched groups ────────────────────────────────────────────────────────

export const unmatchedGroupSchema = z.object({
  groupId: z.number(),
  groupName: z.string(),
  trackCode: z.string(),
  studentInterests: z.array(z.string()),
  studentCount: z.number(),
  students: z.array(groupStudentSchema).optional(),
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
    students: z.array(groupStudentSchema).optional(),
  }),
  recommendedMentor: recommendedMentorSchema.nullable(),
  reason: z.string(),
  score: z.number(),
  scoreBreakdown: mentorScoreBreakdownSchema,
});

export const mentorMatchResponseSchema = z.object({
  data: z.array(mentorGroupRecommendationSchema),
});

// ─── Mentor list ─────────────────────────────────────────────────────────────

export const mentorListItemSchema = z.object({
  mentorId: z.number(),
  name: z.string(),
  trackCode: z.string(),
  institution: z.string().nullable(),
  interests: z.array(z.string()),
  maxGroupCount: z.number(),
  currentAssignedCount: z.number(),
  remainingCapacity: z.number(),
});

export const mentorListResponseSchema = z.object({
  data: z.array(mentorListItemSchema),
});

// ─── Confirm response ────────────────────────────────────────────────────────

export const confirmMentorAssignmentsResponseSchema = z.object({
  msg: z.string(),
  data: z.object({
    confirmedCount: z.number().int().nonnegative(),
  }),
});

// ─── Matched groups (confirmed assignments) ───────────────────────────────────

export const matchedGroupMentorSchema = z.object({
  mentorId: z.number(),
  name: z.string(),
  isActive: z.boolean(),
  trackCode: z.string(),
  institution: z.string().nullable(),
});

export const matchedGroupSchema = z.object({
  membershipId: z.number(),
  groupId: z.number(),
  groupName: z.string(),
  trackCode: z.string(),
  studentCount: z.number().default(0),
  students: z.array(groupStudentSchema).default([]),
  mentor: matchedGroupMentorSchema,
});

export const matchedGroupsResponseSchema = z.object({
  data: z.array(matchedGroupSchema),
});

// ─── Replace mentor response ──────────────────────────────────────────────────

export const replaceMentorResponseSchema = z.object({
  msg: z.string(),
  data: z.object({ replaced: z.number().int().nonnegative() }),
});

// ─── Bulk replace inactive response ──────────────────────────────────────────

export const bulkReplaceInactiveResponseSchema = z.object({
  msg: z.string(),
  data: z.object({
    removedCount: z.number().int().nonnegative(),
    inactiveDays: z.number().int().positive().optional(),
  }),
});

