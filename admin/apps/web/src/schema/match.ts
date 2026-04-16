import { z } from "zod";

export const individualStudentSchema = z.object({
  userId: z.number(),
  firstName: z.string(),
  lastName: z.string(),
  trackId: z.number(),
  trackCode: z.string(),
  yearLevel: z.number().int().nullable(),
  countryName: z.string(),
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

const notFullGroupSchema = recommendationGroupSchema.extend({
  studentCount: z.number().int().nonnegative(),
  availableSeats: z.number().int().nonnegative(),
});

export const matchRecommendationsResponseSchema = z.object({
  data: z
    .union([
      z.array(matchRecommendationSchema),
      z.object({
        recommendations: z.array(matchRecommendationSchema),
        notFullGroups: z.array(notFullGroupSchema),
      }),
    ])
    .transform((value) => {
      if (Array.isArray(value)) {
        return {
          recommendations: value,
          notFullGroups: [],
        };
      }

      return value;
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
export type ConfirmAssignmentsResponse = z.infer<
  typeof confirmAssignmentsResponseSchema
>;
