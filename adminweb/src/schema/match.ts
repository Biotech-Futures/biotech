import { z } from "zod";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function withAliases(
  value: unknown,
  aliases: Record<string, string>,
): unknown {
  if (!isRecord(value)) {
    return value;
  }

  const normalized = { ...value };
  for (const [from, to] of Object.entries(aliases)) {
    if (normalized[to] === undefined && normalized[from] !== undefined) {
      normalized[to] = normalized[from];
    }
  }

  return normalized;
}

const tutorSchema = z.preprocess(
  (value) =>
    withAliases(value, {
      tutor_user_id: "id",
      tutor_name: "name",
    }),
  z
    .object({
      id: z.union([z.string(), z.number()]),
      name: z.string(),
    })
    .nullable()
    .optional(),
);

const recommendationStudentSchema = z.preprocess(
  (value) =>
    withAliases(value, {
      country_name: "country",
      year_level: "yearLevel",
    }),
  z.object({
    id: z.union([z.string(), z.number()]),
    name: z.string().optional(),
    country: z.string().optional(),
    yearLevel: z.number().int().optional(),
    yearlevel: z.number().int().optional(),
    interests: z.array(z.string()).optional(),
  }),
);

const recommendationGroupStudentSchema = recommendationStudentSchema;

const recommendationGroupSchema = z.object({
  id: z.union([z.string(), z.number()]),
  groupName: z.string(),
  maxSize: z.number().int().optional(),
  tutor: tutorSchema,
  groupStudent: z.array(recommendationGroupStudentSchema),
});

const recommendationScoreBreakdownSchema = z.object({
  baseScore: z.number(),
  yearPenalty: z.number(),
  countryPenalty: z.number(),
  timezonePenalty: z.number(),
  sizeBonus: z.number(),
  totalPenalty: z.number(),
  objectiveScore: z.number(),
});

export const matchRecommendationSchema = z.object({
  student: recommendationStudentSchema,
  recommendGroup: recommendationGroupSchema.nullable(),
  reason: z.string(),
  score: z.number(),
  scoreBreakdown: recommendationScoreBreakdownSchema,
});

const recommendedStudentSchema = z.object({
  student: recommendationStudentSchema,
  reason: z.string(),
  score: z.number(),
  scoreBreakdown: recommendationScoreBreakdownSchema,
});

const groupedRecommendationSchema = z.object({
  id: z.union([z.string(), z.number()]),
  groupName: z.string(),
  maxSize: z.number().int().optional(),
  tutor: tutorSchema,
  existingStudents: z.array(recommendationGroupStudentSchema).default([]),
  recommendStudents: z.array(recommendedStudentSchema).default([]),
});

const notFullGroupSchema = recommendationGroupSchema.extend({
  studentCount: z.number().int().nonnegative(),
  availableSeats: z.number().int().nonnegative(),
});

type NormalizedMatchRecommendationsData = {
  recommendations: Array<z.infer<typeof groupedRecommendationSchema>>;
  unmatchedStudents: Array<z.infer<typeof recommendedStudentSchema>>;
  notFullGroups: Array<z.infer<typeof notFullGroupSchema>>;
};

function groupFlatRecommendations(
  recommendations: Array<z.infer<typeof matchRecommendationSchema>>,
) {
  const groupsById = new Map<string, z.infer<typeof groupedRecommendationSchema>>();
  const unmatchedStudents: Array<z.infer<typeof recommendedStudentSchema>> = [];

  for (const recommendation of recommendations) {
    const recommendedStudent = {
      student: recommendation.student,
      reason: recommendation.reason,
      score: recommendation.score,
      scoreBreakdown: recommendation.scoreBreakdown,
    };

    if (!recommendation.recommendGroup) {
      unmatchedStudents.push(recommendedStudent);
      continue;
    }

    const group = recommendation.recommendGroup;
    const groupId = String(group.id);
    const existingGroup = groupsById.get(groupId);

    if (existingGroup) {
      existingGroup.recommendStudents.push(recommendedStudent);
      continue;
    }

    groupsById.set(groupId, {
      id: group.id,
      groupName: group.groupName,
      maxSize: group.maxSize,
      tutor: group.tutor,
      existingStudents: group.groupStudent,
      recommendStudents: [recommendedStudent],
    });
  }

  return {
    recommendations: [...groupsById.values()],
    unmatchedStudents,
  };
}

export const matchRecommendationsResponseSchema = z.object({
  data: z
    .preprocess(
      (value) =>
        withAliases(value, {
          unmatched_students: "unmatchedStudents",
          not_full_groups: "notFullGroups",
        }),
      z.union([
        z.array(matchRecommendationSchema),
        z.object({
          recommendations: z.array(
            z.union([groupedRecommendationSchema, matchRecommendationSchema]),
          ),
          unmatchedStudents: z.array(recommendedStudentSchema).optional(),
          notFullGroups: z.array(notFullGroupSchema).default([]),
        }),
      ]),
    )
    .transform<NormalizedMatchRecommendationsData>((value) => {
      if (Array.isArray(value)) {
        return {
          ...groupFlatRecommendations(value),
          notFullGroups: [],
        };
      }

      const flatRecommendations = value.recommendations.filter(
        (recommendation): recommendation is z.infer<typeof matchRecommendationSchema> =>
          "student" in recommendation,
      );

      if (flatRecommendations.length > 0) {
        return {
          ...groupFlatRecommendations(flatRecommendations),
          notFullGroups: value.notFullGroups,
        };
      }

      const groupedRecommendations = value.recommendations.filter(
        (
          recommendation,
        ): recommendation is z.infer<typeof groupedRecommendationSchema> =>
          !("student" in recommendation),
      );

      return {
        recommendations: groupedRecommendations,
        unmatchedStudents: value.unmatchedStudents ?? [],
        notFullGroups: value.notFullGroups,
      };
    }),
});

export const confirmAssignmentsResponseSchema = z.object({
  msg: z.string(),
  data: z.preprocess(
    (value) => withAliases(value, { assigned_count: "assignedCount" }),
    z.object({
      assignedCount: z.number().int().nonnegative(),
    }),
  ),
});

// ─── Suggested students for a group (scored) ─────────────────────────────────

export const studentSuggestionSchema = z.object({
  studentUserId: z.number(),
  name: z.string(),
  yearLevel: z.number().int().nullable(),
  country: z.string().nullable(),
  score: z.number(),
  sharedInterests: z.array(z.string()),
});

export const studentSuggestionsResponseSchema = z.object({
  data: z.object({
    groupId: z.number(),
    groupName: z.string(),
    isFull: z.boolean(),
    suggestions: z.array(studentSuggestionSchema),
  }),
});

export type StudentSuggestion = z.infer<typeof studentSuggestionSchema>;

export type MatchRecommendationGroup = z.infer<
  typeof groupedRecommendationSchema
>;
export type MatchRecommendedStudent = z.infer<typeof recommendedStudentSchema>;
export type NotFullGroup = z.infer<typeof notFullGroupSchema>;
