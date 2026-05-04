import { z } from "zod";

export const individualStudentSchema = z.object({
  userId: z.number(),
  firstName: z.string(),
  lastName: z.string(),
  trackId: z.number(),
  trackCode: z.string(),
  yearLevel: z.number().int().nullable(),
  countryName: z.string(),
  interests: z.array(z.string()).default([]),
});

export const individualStudentsResponseSchema = z.object({
  data: z.array(individualStudentSchema),
});

const recommendationStudentSchema = z.object({
  id: z.union([z.string(), z.number()]),
  name: z.string().optional(),
  trackId: z.union([z.string(), z.number()]).optional(),
  country: z.string().optional(),
  yearLevel: z.number().int().optional(),
  yearlevel: z.number().int().optional(),
  interests: z.array(z.string()).optional(),
});

const recommendationGroupStudentSchema = recommendationStudentSchema;

const recommendationGroupSchema = z.object({
  id: z.union([z.string(), z.number()]),
  groupName: z.string(),
  trackId: z.union([z.string(), z.number()]),
  maxSize: z.number().int().optional(),
  tutor: z
    .object({
      id: z.union([z.string(), z.number()]),
      name: z.string(),
    })
    .nullable()
    .optional(),
  groupStudent: z.array(recommendationGroupStudentSchema),
});

const recommendationScoreBreakdownSchema = z.object({
  baseScore: z.number(),
  yearPenalty: z.number(),
  countryPenalty: z.number(),
  timezonePenalty: z.number(),
  sizeBonus: z.number().default(0),
  totalPenalty: z.number(),
  objectiveScore: z.number().default(0),
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
  trackId: z.union([z.string(), z.number()]),
  maxSize: z.number().int().optional(),
  tutor: z
    .object({
      id: z.union([z.string(), z.number()]),
      name: z.string(),
    })
    .nullable()
    .optional(),
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
      trackId: group.trackId,
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
    .union([
      z.array(matchRecommendationSchema),
      z.object({
        recommendations: z.array(
          z.union([groupedRecommendationSchema, matchRecommendationSchema]),
        ),
        unmatchedStudents: z.array(recommendedStudentSchema).optional(),
        notFullGroups: z.array(notFullGroupSchema),
      }),
    ])
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
  data: z.object({
    assignedCount: z.number().int().nonnegative(),
  }),
});

export type IndividualStudent = z.infer<typeof individualStudentSchema>;
export type IndividualStudentsResponse = z.infer<
  typeof individualStudentsResponseSchema
>;
export type MatchRecommendation = z.infer<typeof matchRecommendationSchema>;
export type MatchRecommendationGroup = z.infer<
  typeof groupedRecommendationSchema
>;
export type MatchRecommendedStudent = z.infer<typeof recommendedStudentSchema>;
export type NotFullGroup = z.infer<typeof notFullGroupSchema>;
export type ConfirmAssignmentsResponse = z.infer<
  typeof confirmAssignmentsResponseSchema
>;
